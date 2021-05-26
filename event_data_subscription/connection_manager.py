import boto3
import datetime
import json

from aws_xray_sdk.core import patch_all, xray_recorder

from okdata.aws.logging import logging_wrapper, log_add, log_exception
from okdata.resource_auth import ResourceAuthorizer
from okdata.sdk.webhook.client import WebhookClient
from okdata.sdk.config import Config
from requests.exceptions import HTTPError

patch_all()

origo_config = Config()
origo_config.config["cacheCredentials"] = False
webhook_client = WebhookClient(config=origo_config)
resource_authorizer = ResourceAuthorizer()

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
            if auth_token:
                has_access = resource_authorizer.has_access(
                    auth_token,
                    scope="okdata:dataset:read",
                    resource_name=f"okdata:dataset:{dataset_id}",
                )
                forbidden_msg = "Forbidden"
            else:
                auth_response = webhook_client.authorize_webhook_token(
                    dataset_id, webhook_token, "read", retries=3
                )
                has_access = auth_response["access"]
                forbidden_msg = auth_response["reason"]

            log_add(has_dataset_access=has_access)

            if not has_access:
                return error_response(403, forbidden_msg)

        except HTTPError as e:
            log_exception(e)
            if e.response.status_code == 401:
                return {"statusCode": 401, "body": "Unauthorized"}
            return {"statusCode": 500, "body": "Error occured during connect"}

        subscriptions_table.put_item(
            Item={
                "connection_id": connection_id,
                "dataset_id": dataset_id,
                "connected_at": str(
                    datetime.datetime.utcnow()
                    .replace(tzinfo=datetime.timezone.utc)
                    .isoformat()
                ),
            }
        )

        return {"statusCode": 200, "body": "Connected"}

    elif event_type == "DISCONNECT":
        subscriptions_table.delete_item(Key={"connection_id": connection_id})

        return {"statusCode": 200, "body": "Disconnected"}

    else:
        return {"statusCode": 500, "body": "Unrecognized event type"}


def error_response(status_code: int, msg: str):
    return {"statusCode": status_code, "body": json.dumps({"message": msg})}
