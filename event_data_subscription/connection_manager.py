# import json
import boto3
import datetime
from boto3.dynamodb.conditions import Key

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

dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
subscriptions_table_name = "event-data-subscriptions"
subscriptions_table = dynamodb.Table(subscriptions_table_name)


@logging_wrapper
@xray_recorder.capture("handle")
def handle(event, context):
    # SimpleDatasetAuthorizerClient.check_dataset_access(dataset_id, bearer_token=bearer_token)
    # has_access = auth_client.check_dataset_access(dataset_id, bearer_token="<token for en annen bruker>")

    event_type = event["requestContext"]["eventType"]
    connection_id = event["requestContext"]["connectionId"]

    log_add(event_type=event_type, connection_id=connection_id)

    if event_type == "CONNECT":
        dataset_id = event.get("queryStringParameters", {}).get("dataset_id")

        if not dataset_id:
            return {"statusCode": 400, "body": "Bad request"}

        log_add(dataset_id=dataset_id)

        subscriptions_table.put_item(
            Item={
                "connection_id": connection_id,
                "dataset_id": dataset_id,
                "connected_at": datetime.datetime.utcnow().isoformat(),
            }
        )

        return {"statusCode": 200, "body": "Connected"}

    elif event_type == "DISCONNECT":
        subscriptions_table.delete_item(Key={"connection_id": connection_id})

        return {"statusCode": 200, "body": "Disconnected"}

    else:
        return {"statusCode": 500, "body": "Unrecognized event type"}
