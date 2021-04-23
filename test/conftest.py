import json
import boto3
import pytest
import base64
from unittest.mock import Mock
from moto import mock_dynamodb2
from requests.exceptions import HTTPError

from okdata.sdk.dataset_authorizer.simple_dataset_authorizer_client import (
    SimpleDatasetAuthorizerClient,
)

from event_data_subscription.connection_manager import (
    subscriptions_table_name as table_name,
)

from event_data_subscription.publish_event import api_gateway_client


auth_token = "AbcdefghijklmnoP12345="
bad_auth_token = "eyJhbGciOiJSUzI1N"
dataset_id = "test-event-subscription"
dataset_id_no_subs = "dataset-no-subscriber"
connection_id = "UqoGzdQVUkwCljw="
datetime_now = "2020-01-01T12:00:00.123456+00:00"
stream_arn = f"arn:aws:kinesis:eu-west-1:123456789101:stream/dp.green.{dataset_id}.incoming.1.json"
stream_arn_ignore = f"arn:aws:kinesis:eu-west-1:123456789101:stream/dp.green.{dataset_id_no_subs}.incoming.1.json"


def create_subscriptions_table(items=[], region="eu-west-1"):
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
def mock_auth(monkeypatch):
    def check_token(self, dataset_id, bearer_token):
        return {"access": True if bearer_token == auth_token else False}

    monkeypatch.setattr(
        SimpleDatasetAuthorizerClient, "check_dataset_access", check_token
    )
    monkeypatch.setattr(
        SimpleDatasetAuthorizerClient, "authorize_webhook_token", check_token
    )


@pytest.fixture(scope="function")
def mock_auth_error(monkeypatch):
    def check_token(self, dataset_id, bearer_token):
        e = HTTPError()
        e.response = Mock(status_code=401)
        raise e

    monkeypatch.setattr(
        SimpleDatasetAuthorizerClient, "check_dataset_access", check_token
    )


@pytest.fixture(scope="function")
def mock_dynamodb():
    mock_dynamodb2().start()


@pytest.fixture(scope="function")
def mock_api_gateway(monkeypatch):
    def post_event(**kwargs):
        pass

    monkeypatch.setattr(api_gateway_client, "post_to_connection", post_event)
