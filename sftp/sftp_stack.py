import sys
import os
import boto3
import json
from os.path import join

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_transfer as transfer,
    aws_logs as logs,
    # aws_s3 as s3,
    aws_efs as efs,
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
        role_prefix: str = "",
        policy_prefix: str = "",
        instance_profile_prefix: str = "",
        role_path: str = "",
    ):
        self.role_prefix = role_prefix
        self.policy_prefix = policy_prefix
        self.instance_profile_prefix = instance_profile_prefix
        self.role_path = role_path

    def visit(self, node: IConstruct):
        if not (
            CfnResource.is_cfn_resource(node)
            and node.cfn_resource_type in self.resource_types
        ):
            return

        resource_type = node.cfn_resource_type
        resource_id = self._get_resource_id(node.node.path)

        if "IAM::Role" in resource_type or "IAM::InstanceProfile" in resource_type:
            role_path_override = self.role_path or ""

        if (self.role_path or self.role_prefix) and "IAM::Role" in resource_type:
            try:
                role_name = node.role_name

            except Exception as exc:
                role_name = node.node.addr

            if self.role_prefix and not role_name.startswith(self.role_prefix):
                node.add_property_override(
                    "RoleName", f"{self.role_prefix}{resource_id}"[:64]
                )
            if role_path_override:
                node.add_property_override("Path", role_path_override)

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
            if role_path_override:
                node.add_property_override("Path", role_path_override)

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
        # role_name_prefix = "Network"
        # Aspects.of(self).add(
        #     IamNamingAspect(
        #         role_prefix=role_name_prefix,
        #         policy_prefix=role_name_prefix,
        #         instance_profile_prefix=role_name_prefix,
        #     )
        # )

        iam_role_path = self.node.try_get_context("IamRolePath") or "/"
        if iam_role_path[-1] != "/":
            iam_role_path += "/"

        Aspects.of(self).add(IamNamingAspect(role_path=iam_role_path))

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

        sftp_security_group = ec2.SecurityGroup(self, "SftpSecurityGroup", vpc=vpc)
        for cidr in cidr_ranges:
            sftp_security_group.add_ingress_rule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(22))

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

        efs_security_group = ec2.SecurityGroup(self, "EfsAccess", vpc=vpc)

        # allow connections on the NFS port from inside the VPC
        nfs_port = ec2.Port.tcp(2049)  # NFS port
        for cidr_range in cidr_ranges:
            efs_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(cidr_range), connection=nfs_port
            )

        file_system_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["elasticfilesystem:Client*"],
                    principals=[iam.AnyPrincipal()],
                    # conditions={
                    #     "Bool": {"elasticfilesystem:AccessedViaMountTarget": "true"}
                    # },
                )
            ]
        )

        fs = efs.FileSystem(
            self,
            "Backup",
            file_system_name="FmcBackup",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnets=[
                    ec2.Subnet.from_subnet_id(self, "efs-" + subnet_id, subnet_id)
                    for subnet_id in subnet_ids
                ]
            ),
            security_group=efs_security_group,
            removal_policy=RemovalPolicy.RETAIN,
            enable_automatic_backups=True,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_30_DAYS,
            encrypted=True,
            file_system_policy=file_system_policy,
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
            pre_authentication_login_banner="your papers, please\n",
            # post_authentication_login_banner="your papers appear to be in order",
            endpoint_details=transfer.CfnServer.EndpointDetailsProperty(
                vpc_id=vpc.vpc_id,
                security_group_ids=[sftp_security_group.security_group_id],
                subnet_ids=subnet_ids,
            ),
            domain="EFS",
            identity_provider_type="SERVICE_MANAGED",  # AWS_DIRECTORY_SERVICE
            endpoint_type="VPC",
            protocols=["SFTP"],
            logging_role=logging_role.role_arn,
            # structured_log_destinations=[log_group.log_group_arn],
        )

        user_role = iam.Role(
            self,
            "TransferUserRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
            inline_policies={
                "logs": logging_policy,
                "efs": iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "elasticfilesystem:Describe*",
                                "elasticfilesystem:List*",
                                "elasticfilesystem:ClientWrite",
                                "elasticfilesystem:ClientRootAccess",
                                "elasticfilesystem:ClientMount",
                            ],
                            resources=[fs.file_system_arn],
                        ),
                    ],
                ),
            },
        )

        home = os.environ.get("HOME")
        user_info = self.node.try_get_context("Users") or {}
        group_id = 501  # set in parameter?

        for username, details in user_info.items():
            filename = details["SshKeyFile"]
            user_id = details["UserId"]

            if filename[0] == "/":
                path = filename
            else:
                # look for the ssh public key file in  ~/.ssh
                path = join(home, ".ssh", filename)

            ssh_keys = []
            with open(path) as fp:
                for line in fp.readlines():
                    ssh_keys.append(line.strip())

            # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-transfer-user.html
            user = transfer.CfnUser(
                self,
                f"CfnUser-{username}",
                role=user_role.role_arn,
                server_id=server.attr_server_id,
                user_name=username,
                ssh_public_keys=ssh_keys,
                home_directory=f"/{fs.file_system_id}/{username}/",
                posix_profile={"uid": user_id, "gid": group_id}
                # policy
                # home_directory_type
            )

        # create NLB. accept tcp 22. register endpoints.
        # custom resource to extract endpoints from server.

        CfnOutput(
            self,
            "SftpServerAddress",
            value=f"{server.attr_server_id}.server.transfer.{self.region}.amazonaws.com",
        )

        # fs-0e4fbfe7c23653044.efs.us-east-1.amazonaws.com
        CfnOutput(
            self,
            "FileSystemAddress",
            value=f"{fs.file_system_id}.efs.{self.region}.amazonaws.com",
        )
        # CfnOutput(
        #     self,
        #     "SftpBucketName",
        #     value="s3://" + bucket_name,
        # )
        CfnOutput(
            self,
            "SftpUserRole",
            value=user_role.role_arn,
        )

        # CfnOutput(
        #     self,
        #     "SftpEndpointDetails",
        #     value=json.dumps(server.endpoint_details),
        # )
