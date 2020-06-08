import os
import base64
import boto3
from boto3.dynamodb.conditions import Key
from aws_xray_sdk.core import patch_all, xray_recorder
from dataplatform.awslambda.logging import logging_wrapper, log_add, log_exception

patch_all()

socket_endpoint_url = os.environ["WEBSOCKET_ENDPOINT"]

api_gateway_client = boto3.client(
    "apigatewaymanagementapi", endpoint_url=socket_endpoint_url, region_name="eu-west-1"
)

dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
event_data_subscriptions_table = dynamodb.Table("event-data-subscriptions")


@logging_wrapper
@xray_recorder.capture("handle")
def handle(event, context):
    for record in event["Records"]:
        try:
            route_data_to_subscribers(record)
        except Exception as e:
            log_exception(e)


def route_data_to_subscribers(record):
    source_stream_arn = record["eventSourceARN"]
    dataset_id = resolve_dataset_id(source_stream_arn)
    log_add(dataset_id=dataset_id)

    event_data = base64.b64decode(record["kinesis"]["data"])

    subscriber_connection_ids = get_subscriber_connections_ids(dataset_id)
    for connection_id in subscriber_connection_ids:
        try:
            api_gateway_client.post_to_connection(
                ConnectionId=connection_id, Data=event_data
            )
        except Exception as e:
            log_exception(e)


def get_subscriber_connections_ids(dataset_id):
    query_result = event_data_subscriptions_table.query(
        KeyConditionExpression=Key("dataset_id").eq(dataset_id), IndexName="ByDatasetId"
    )
    return [item["connection_id"] for item in query_result["Items"]]


def resolve_dataset_id(stream_arn):
    [arn_prefix, stream_name] = stream_arn.split("/")
    [
        prefix,
        conf,
        dataset_id,
        processing_stage,
        version,
        data_format,
    ] = stream_name.split(".")
    return dataset_id
