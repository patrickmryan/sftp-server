import os
from aws_cdk import App, Environment, LegacyStackSynthesizer
from sftp.sftp_stack import SftpStack

env = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

app = App()
SftpStack(
    app,
    "SftpStack",
    env=env,
    synthesizer=LegacyStackSynthesizer(),
)

app.synth()
