import json

from aws_xray_sdk.core import patch_all, xray_recorder
from dataplatform.awslambda.logging import logging_wrapper, log_add

# from origo.dataset_authorizer.simple_dataset_authorizer_client import (
#     SimpleDatasetAuthorizerClient,
# )
# from origo.config import Config

patch_all()

# origo_config = Config()
# origo_config.config["cacheCredentials"] = True
# auth_client = SimpleDatasetAuthorizerClient()  # config=origo_config)

# dynamodb = resource("dynamodb", region_name="eu-west-1")
# log_aggregator_table = dynamodb.Table("event-subscribers")


@logging_wrapper
@xray_recorder.capture("handle")
def handle(event, context):
    # SimpleDatasetAuthorizerClient.check_dataset_access(dataset_id, bearer_token=bearer_token)
    # has_access = auth_client.check_dataset_access(dataset_id, bearer_token="<token for en annen bruker>")

    event_type = event["requestContext"]["eventType"]
    connection_id = event["requestContext"]["connectionId"]

    log_add(event_type=event_type, connection_id=connection_id)

    return {"statusCode": 200, "body": json.dumps({"response": "hello"})}

    """
    if event_type == "CONNECT":
        # handle connect
        pass

    elif event_type == "DISCONNECT":
        # handle disconnect
        pass

    else:
        # handle
    """
