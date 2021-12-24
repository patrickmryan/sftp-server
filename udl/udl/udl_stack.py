from aws_cdk import (
    Duration,
    Stack,
    CfnParameter,
    # aws_sqs as sqs,
    aws_lambda as _lambda,
    # aws_iam as iam,
)
from constructs import Construct

class UdlStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        udl_credential = CfnParameter(self,
                "UDLcredential", type="String",
                description="Access credentials encoded using base64")

        runtime = _lambda.Runtime.PYTHON_3_9
        
        pandas_layer = _lambda.LayerVersion(
                self, 'PandasLayer',
                code=_lambda.Code.from_asset('layer'),
                compatible_runtimes=[runtime],
                description='pandas library',
                )

        read_udl_lambda = _lambda.Function(
                self, 'UdlRead',
                runtime=runtime,
                code=_lambda.Code.from_asset('udl_read'),
                handler='udl_read.lambda_handler',
                environment= {
                    'CREDENTIAL' : udl_credential.value_as_string
                },
                layers = [ pandas_layer ]
                # role=lambda_role
            )