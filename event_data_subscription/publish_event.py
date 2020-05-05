from aws_xray_sdk.core import patch_all, xray_recorder
from dataplatform.awslambda.logging import logging_wrapper

patch_all()


@logging_wrapper
@xray_recorder.capture("handle")
def handle(event, context):
    pass
