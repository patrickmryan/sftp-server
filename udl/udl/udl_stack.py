from aws_cdk import (
    Duration,
    Stack,
    # aws_sqs as sqs,
    aws_lambda as _lambda,
    # aws_iam as iam,
)
from constructs import Construct

class UdlStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self, 'PermissionBoundaryLambda', "T_PROJADMIN_U")
        # iam.PermissionsBoundary.of(self).apply(permissions_boundary)

        read_udl_lambda = _lambda.Function(
                self, 'UdlRead',
                runtime=_lambda.Runtime.PYTHON_3_7,
                code=_lambda.Code.from_asset('udl_read'),
                handler='udl_read.handler',
                environment= {
                    'CREDENTIAL' : 'cGF0cmljay5yeWFuOlRheWwwclN3aWZ0ITIwMjI='
                }
                # role=lambda_role
            )