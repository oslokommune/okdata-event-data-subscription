import base64
import json
from unittest.mock import Mock

import boto3
import pytest
from moto import mock_dynamodb2
from okdata.resource_auth import ResourceAuthorizer
from okdata.sdk.webhook.client import WebhookClient
from requests.exceptions import HTTPError

auth_token = "AbcdefghijklmnoP12345="
auth_token_unauthorized = "eyJhbGciOiJSUzI1N"
auth_token_bad = "foo"
dataset_id = "test-event-subscription"
dataset_id_no_subs = "dataset-no-subscriber"
connection_id = "UqoGzdQVUkwCljw="
datetime_now = "2020-01-01T12:00:00.123456+00:00"
stream_arn = f"arn:aws:kinesis:eu-west-1:123456789101:stream/dp.green.{dataset_id}.incoming.1.json"
stream_arn_ignore = f"arn:aws:kinesis:eu-west-1:123456789101:stream/dp.green.{dataset_id_no_subs}.incoming.1.json"


def create_subscriptions_table(items=[], region="eu-west-1"):
    from event_data_subscription.connection_manager import (
        subscriptions_table_name as table_name,
    )

    client = boto3.client("dynamodb", region_name=region)
    client.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "connection_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "connection_id", "AttributeType": "S"},
            {"AttributeName": "dataset_id", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        GlobalSecondaryIndexes=[
            {
                "IndexName": "ByDatasetId",
                "KeySchema": [{"AttributeName": "dataset_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 1,
                    "WriteCapacityUnits": 1,
                },
            }
        ],
    )

    table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    for item in items:
        table.put_item(Item=item)

    return table


def connection_event(
    event_type, connection_id, dataset_id, bearer_token=None, webhook_token=None
):
    event = {
        "queryStringParameters": {},
        "headers": {},
        "requestContext": {"eventType": event_type, "connectionId": connection_id},
    }

    if dataset_id:
        event["queryStringParameters"]["dataset_id"] = dataset_id

    if bearer_token:
        event["headers"]["Authorization"] = f"Bearer {bearer_token}"

    if webhook_token:
        event["queryStringParameters"]["webhook_token"] = webhook_token

    return event


kinesis_event = {
    "Records": [
        {
            "eventSourceARN": stream_arn,
            "kinesis": {
                "data": base64.b64encode(json.dumps({"hello": "world"}).encode("utf-8"))
            },
        },
        {
            "eventSourceARN": stream_arn_ignore,
            "kinesis": {
                "data": base64.b64encode(json.dumps({"foo": "bar"}).encode("utf-8"))
            },
        },
    ]
}


@pytest.fixture(scope="function")
def mock_resource_auth(monkeypatch):
    def check_token(self, token, scope, resource_name):
        if token == auth_token_bad:
            e = HTTPError()
            e.response = Mock(status_code=401)
            raise e
        return token == auth_token

    monkeypatch.setattr(ResourceAuthorizer, "has_access", check_token)


@pytest.fixture(scope="function")
def mock_webhook_auth(monkeypatch):
    def authorize_webhook_token(self, dataset_id, token, operation, retries):
        if token == auth_token and operation == "read":
            return {"access": True, "reason": None}
        return {"access": False, "reason": "Forbidden"}

    monkeypatch.setattr(
        WebhookClient, "authorize_webhook_token", authorize_webhook_token
    )


@pytest.fixture(scope="function")
def mock_auth(mock_resource_auth, mock_webhook_auth):
    pass


@pytest.fixture(scope="function")
def mock_dynamodb():
    mock_dynamodb2().start()


@pytest.fixture(scope="function")
def mock_api_gateway(monkeypatch):
    from event_data_subscription.publish_event import api_gateway_client

    def post_event(**kwargs):
        pass

    monkeypatch.setattr(api_gateway_client, "post_to_connection", post_event)
