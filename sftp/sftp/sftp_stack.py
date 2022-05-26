import sys
import boto3

from aws_cdk import (
    # Duration,
    Stack,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_transfer as transfer,
    aws_elasticloadbalancingv2 as elb,
)
from constructs import Construct


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
        if permissions_boundary_policy_arn:
            policy = iam.ManagedPolicy.from_managed_policy_arn(
                self, "PermissionsBoundary", permissions_boundary_policy_arn
            )
            iam.PermissionsBoundary.of(self).apply(policy)

        key = "VpcName"
        vpc_name = self.node.try_get_context(key)
        if not vpc_name:
            print("missing context variable " + key)
            sys.exit(1)

        key = "CidrRanges"
        cidr_ranges = self.node.try_get_context(key)
        if not cidr_ranges:
            cidr_ranges = []

        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_name=vpc_name)
        subnets = vpc.private_subnets
        subnet_ids = [subnet.subnet_id for subnet in subnets]

        security_group = ec2.SecurityGroup(self, "SftpSecurityGroup", vpc=vpc)
        for cidr in cidr_ranges:
            security_group.add_ingress_rule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(22))

        # nlb = elb.NetworkLoadBalancer(self, 'NLB', vpc=vpc, vpc_subnets=subnets)

        # vpc_endpoint = ec2.VpcEndpoint(self, 'VpcEndpoint')

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
            endpoint_type="VPC",  # nope 'VPC_ENDPOINT',
            protocols=["SFTP"],
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
