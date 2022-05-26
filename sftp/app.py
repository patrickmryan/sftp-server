#!/usr/bin/env python3
import os

import aws_cdk as cdk

from sftp.sftp_stack import SftpStack

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

app = cdk.App()
SftpStack(app, "SftpStack", env=env)

app.synth()
