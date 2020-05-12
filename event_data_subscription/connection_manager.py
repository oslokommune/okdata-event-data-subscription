import boto3
import datetime

from requests.exceptions import HTTPError
from aws_xray_sdk.core import patch_all, xray_recorder
from dataplatform.awslambda.logging import logging_wrapper, log_add, log_exception

from origo.dataset_authorizer.simple_dataset_authorizer_client import (
    SimpleDatasetAuthorizerClient,
)
from origo.config import Config

patch_all()

origo_config = Config()
origo_config.config["cacheCredentials"] = False
auth_client = SimpleDatasetAuthorizerClient(config=origo_config)

dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
subscriptions_table_name = "event-data-subscriptions"
subscriptions_table = dynamodb.Table(subscriptions_table_name)


def get_bearer_token(header):
    auth_type, _, token = header.partition(" ")
    if auth_type.lower() == "bearer" and token:
        return token


@logging_wrapper
@xray_recorder.capture("handle")
def handle(event, context):
    event_type = event["requestContext"]["eventType"]
    connection_id = event["requestContext"]["connectionId"]

    log_add(event_type=event_type, connection_id=connection_id)

    if event_type == "CONNECT":
        auth_token = get_bearer_token(event["headers"].get("Authorization", ""))
        query_params = event.get("queryStringParameters", {})
        dataset_id = query_params.get("dataset_id")
        webhook_token = query_params.get("webhook_token")

        log_add(dataset_id=dataset_id)

        if not dataset_id or not any([auth_token, webhook_token]):
            return {"statusCode": 400, "body": "Bad request"}

        try:
            has_access = (
                auth_client.check_dataset_access(dataset_id, bearer_token=auth_token)
                if auth_token
                else auth_client.authorize_webhook_token(dataset_id, webhook_token)
            ).get("access", False)
        except HTTPError as e:
            log_exception(e)
            if e.response.status_code == 401:
                return {"statusCode": 401, "body": "Unauthorized"}
            else:
                return {
                    "statusCode": 500,
                    "body": f"Error occured during connect. RequestId: {context.aws_request_id}",
                }

        log_add(has_dataset_access=has_access)

        if not has_access:
            return {"statusCode": 403, "body": "Forbidden"}

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
