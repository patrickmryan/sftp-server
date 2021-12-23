from aws_cdk import (
    Duration,
    Stack,
    aws_sqs as sqs,
    # aws_iam as iam,
)
from constructs import Construct

class UdlStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self, 'PermissionBoundaryLambda', "T_PROJADMIN_U")
        # iam.PermissionsBoundary.of(self).apply(permissions_boundary)


        # The code that defines your stack goes here

        # example resource
        queue = sqs.Queue(
            self, "UdlQueue",
            visibility_timeout=Duration.seconds(300),
        )
