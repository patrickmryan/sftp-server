import sys
import boto3

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_transfer as transfer,
    aws_s3 as s3,
    Aspects,
    IAspect,
    CfnResource,
    CfnOutput,
)
from constructs import Construct, IConstruct
import jsii


@jsii.implements(IAspect)
class IamNamingAspect:
    """Adds prefixes to Role-, Policy-, and IP-names."""

    resource_types = [
        "AWS::IAM::Role",
        "AWS::IAM::Policy",
        "AWS::IAM::ManagedPolicy",
        "AWS::IAM::InstanceProfile",
    ]

    def __init__(
        self,
        role_prefix: str = "Network",
        policy_prefix: str = "Network",
        instance_profile_prefix: str = "Network",
    ):
        self.role_prefix = role_prefix
        self.policy_prefix = policy_prefix
        self.instance_profile_prefix = instance_profile_prefix

    def visit(self, node: IConstruct):
        if not (
            CfnResource.is_cfn_resource(node)
            and node.cfn_resource_type in self.resource_types
        ):
            return

        resource_type = node.cfn_resource_type
        resource_id = self._get_resource_id(node.node.path)
        if "IAM::Role" in resource_type:
            try:
                role_name = node.role_name
            except Exception:
                role_name = node.node.addr
            if not role_name.startswith(self.role_prefix):
                node.add_property_override(
                    "RoleName", f"{self.role_prefix}{resource_id}"[:64]
                )
        elif "IAM::Policy" in resource_type:
            if not node.policy_name.startswith(self.policy_prefix):
                node.add_property_override(
                    "PolicyName",
                    f"{self.policy_prefix}{resource_id}"[:128],
                )
        elif "IAM::ManagedPolicy" in resource_type:
            if not node.managed_policy_name.startswith(self.policy_prefix):
                node.add_property_override(
                    "ManagedPolicyName",
                    f"{self.policy_prefix}{resource_id}"[:128],
                )
        elif "IAM::InstanceProfile" in resource_type:
            node.add_property_override(
                "InstanceProfileName",
                f"{self.instance_profile_prefix}{resource_id}"[:128],
            )

    def _get_resource_id(self, resource_path):
        path_split = [x.replace(":", "") for x in resource_path.split("/")]
        return "-".join(path_split)


class SftpStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # context params:
        #  vpc name
        #  CIDRs for security group  (create PrefixList)
        #  perm boundary (optional)

        permissions_boundary_policy_arn = self.node.try_get_context(
            "PermissionsBoundaryPolicyArn"
        )

        if not permissions_boundary_policy_arn:
            permissions_boundary_policy_name = self.node.try_get_context(
                "PermissionsBoundaryPolicyName"
            )
            if permissions_boundary_policy_name:
                permissions_boundary_policy_arn = self.format_arn(
                    service="iam",
                    region="",
                    account=self.account,
                    resource="policy",
                    resource_name=permissions_boundary_policy_name,
                )

        if permissions_boundary_policy_arn:
            policy = iam.ManagedPolicy.from_managed_policy_arn(
                self, "PermissionsBoundary", permissions_boundary_policy_arn
            )
            iam.PermissionsBoundary.of(self).apply(policy)

        # need this in role names
        role_name_prefix = "Network"
        Aspects.of(self).add(
            IamNamingAspect(
                role_prefix=role_name_prefix,
                policy_prefix=role_name_prefix,
                instance_profile_prefix=role_name_prefix,
            )
        )

        key = "VpcId"
        vpc_id = self.node.try_get_context(key)
        if not vpc_id:
            print("missing context variable " + key)
            sys.exit(1)

        key = "CidrRanges"
        cidr_ranges = self.node.try_get_context(key)
        if not cidr_ranges:
            cidr_ranges = []

        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)
        subnet_ids = self.node.try_get_context("SubnetIds")

        security_group = ec2.SecurityGroup(self, "SftpSecurityGroup", vpc=vpc)
        for cidr in cidr_ranges:
            security_group.add_ingress_rule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(22))

        logging_policy = iam.PolicyDocument(
            assign_sids=True,
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=["*"],
                )
            ],
        )

        bucket_name = self.node.try_get_context("BucketName")

        bucket = s3.Bucket.from_bucket_attributes(
            self, "TransferBucket", bucket_name=bucket_name
        )

        user_role = iam.Role(
            self,
            "TransferUserRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
            inline_policies={
                "logs": logging_policy,
                # https://aws.amazon.com/blogs/storage/simplify-your-aws-sftp-structure-with-chroot-and-logical-directories/
                "s3": iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:ListBucket*",
                            ],
                            resources=[bucket.bucket_arn],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:PutObject*",
                                "s3:GetObject*",
                                "s3:DeleteObject",  # needed for test
                            ],
                            resources=[bucket.arn_for_objects("*")],
                        ),
                    ],
                ),
            },
        )

        logging_role = iam.Role(
            self,
            "TransferLoggingRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
            inline_policies={"logs": logging_policy},
        )

        server = transfer.CfnServer(
            self,
            "SftpServer",
            pre_authentication_login_banner="""
a very important sftp server
""",
            post_authentication_login_banner="""
This is a US Government server.
""",
            endpoint_details=transfer.CfnServer.EndpointDetailsProperty(
                vpc_id=vpc.vpc_id,
                security_group_ids=[security_group.security_group_id],
                subnet_ids=subnet_ids,
            ),
            endpoint_type="VPC",
            protocols=["SFTP"],
            logging_role=logging_role.role_arn,
        )

        # create NLB. accept tcp 22. point to endpoints.

        CfnOutput(
            self,
            "SftpServerAddress",
            value=f"{server.attr_server_id}.server.transfer.{self.region}.amazonaws.com",
        )
        CfnOutput(
            self,
            "SftpBucketName",
            value="s3://" + bucket_name,
        )
        CfnOutput(
            self,
            "SftpUserRole",
            value=user_role.role_arn,
        )

        # CfnOutput(
        #     self,
        #     "SftpEndpointDetails",
        #     value=server.endpoint_details,
        # )
