import base64

from aws_xray_sdk.core import xray_recorder

from test.conftest import (
    kinesis_event,
    stream_arn,
    stream_arn_ignore,
    create_subscriptions_table,
    datetime_now,
    connection_id,
    dataset_id,
    dataset_id_no_subs,
)


xray_recorder.begin_segment("Test")


class TestPublishEvent:
    def test_publish_events_handle(self, mocker):
        import event_data_subscription.publish_event as publish_event

        mocker.patch(
            "event_data_subscription.publish_event.api_gateway_client.post_to_connection"
        )
        mocker.spy(publish_event, "route_data_to_subscribers")

        connected_client_item = {
            "connection_id": connection_id,
            "dataset_id": dataset_id,
            "connected_at": datetime_now,
        }
        create_subscriptions_table(items=[connected_client_item])

        publish_event.handle(kinesis_event, {})

        assert publish_event.route_data_to_subscribers.call_count == len(
            kinesis_event["Records"]
        )

        event_data = base64.b64decode(kinesis_event["Records"][0]["kinesis"]["data"])

        publish_event.api_gateway_client.post_to_connection.assert_called_once_with(
            ConnectionId=connection_id, Data=event_data
        )

    def test_get_subscriber_connections_ids(self, mock_dynamodb):
        import event_data_subscription.publish_event as publish_event

        create_subscriptions_table(
            items=[
                {
                    "connection_id": connection_id,
                    "dataset_id": dataset_id,
                    "connected_at": datetime_now,
                },
                {
                    "connection_id": "fooBarId=",
                    "dataset_id": "not-matched-dataset",
                    "connected_at": datetime_now,
                },
            ]
        )

        connection_ids = publish_event.get_subscriber_connections_ids(dataset_id)

        assert len(connection_ids) == 1
        assert connection_id in connection_ids

    def test_resolve_dataset_id(self):
        import event_data_subscription.publish_event as publish_event

        assert publish_event.resolve_dataset_id(stream_arn) == dataset_id
        assert publish_event.resolve_dataset_id(stream_arn_ignore) == dataset_id_no_subs
