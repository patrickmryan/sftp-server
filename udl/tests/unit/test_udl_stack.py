import aws_cdk as core
import aws_cdk.assertions as assertions

from udl.udl_stack import UdlStack

# example tests. To run these tests, uncomment this file along with the example
# resource in udl/udl_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = UdlStack(app, "udl")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
