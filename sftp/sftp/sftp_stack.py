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

        # subnets = vpc.private_subnets
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
            inline_policies={"logs": logging_policy},
        )
        bucket.grant_read_write(user_role)  # objects_key_pattern

        #  - Effect: Allow
        #     Action:
        #       - s3:PutObject*
        #       - s3:GetObject*
        #     Resource: !Sub '${SftpBucket.Arn}/*'
        #   - Effect: Allow
        #     Action:
        #       - s3:List*
        #     Resource: !Sub '${SftpBucket.Arn}'
        #   - Effect: Allow
        #     Action: 'events:*'
        #     Resource: '*'
        #   - Effect: Allow
        #     Action:
        #       - logs:CreateLogStream
        #       - logs:DescribeLogStreams
        #       - logs:CreateLogGroup
        #       - logs:PutLogEvents
        #     Resource: '*'

        logging_role = iam.Role(
            self,
            "TransferLoggingRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
            inline_policies={"logs": logging_policy},
        )

        vpc_endpoint = ec2.CfnVPCEndpoint(
            self,
            "VpcEndpoint",
            service_name=f"com.amazonaws.{self.region}.transfer",
            vpc_id=vpc.vpc_id,
            subnet_ids=subnet_ids,
            vpc_endpoint_type="Interface",
        )

        server = transfer.CfnServer(
            self,
            "SftpServer",
            pre_authentication_login_banner="a very important sftp server",
            endpoint_details=transfer.CfnServer.EndpointDetailsProperty(
                vpc_id=vpc.vpc_id,
                security_group_ids=[security_group.security_group_id],
                subnet_ids=subnet_ids,
                # vpc_endpoint_id=vpc_endpoint.ref,
                # address_allocation_ids=["addressAllocationIds"],
            ),
            endpoint_type="VPC",
            protocols=["SFTP"],
            logging_role=logging_role.role_arn,
        )


# SftpServer:
#   Type: AWS::Transfer::Server
#   Properties:
#     EndpointType: VPC
#     EndpointDetails:
#       AddressAllocationIds:
#         - !GetAtt SftpPublicIp1.AllocationId
#         - !GetAtt SftpPublicIp2.AllocationId
#       VpcId: !Ref VpcId
#       SubnetIds:
#         - !Ref SubnetId1
#         - !Ref SubnetId2
#       SecurityGroupIds:
#         - !GetAtt AllowedSecurityGroup.GroupId
#     Protocols:
#       - SFTP
