from freezegun import freeze_time
from aws_xray_sdk.core import xray_recorder

import event_data_subscription.connection_manager as connection_manager

from test.conftest import (
    connection_event,
    create_subscriptions_table,
    datetime_now,
    auth_token,
    auth_token_unauthorized,
    auth_token_bad,
    connection_id,
    dataset_id,
)


xray_recorder.begin_segment("Test")


class TestConnectionManager:
    @freeze_time(datetime_now)
    def test_connect_ok_bearer(self, mock_auth, mock_dynamodb):
        table = create_subscriptions_table()

        response = connection_manager.handle(
            connection_event(
                "CONNECT", connection_id, dataset_id, bearer_token=auth_token
            ),
            {},
        )

        assert response["statusCode"] == 200
        assert response["body"] == "Connected"

        connection_item = table.scan()["Items"][0]

        assert connection_item == {
            "connection_id": connection_id,
            "dataset_id": dataset_id,
            "connected_at": datetime_now,
        }

    @freeze_time(datetime_now)
    def test_connect_ok_webhook(self, mock_auth, mock_dynamodb):
        table = create_subscriptions_table()

        response = connection_manager.handle(
            connection_event(
                "CONNECT", connection_id, dataset_id, webhook_token=auth_token
            ),
            {},
        )

        assert response["statusCode"] == 200
        assert response["body"] == "Connected"

        connection_item = table.scan()["Items"][0]

        assert connection_item == {
            "connection_id": connection_id,
            "dataset_id": dataset_id,
            "connected_at": datetime_now,
        }

    def test_connect_bad_auth(self, mock_auth, mock_dynamodb):
        no_auth_event = connection_event("CONNECT", connection_id, dataset_id)
        webhook_auth_event = connection_event(
            "CONNECT", connection_id, dataset_id, webhook_token=auth_token_unauthorized
        )
        bearer_auth_event = connection_event(
            "CONNECT", connection_id, dataset_id, bearer_token=auth_token_unauthorized
        )
        webhook_auth_event = connection_event(
            "CONNECT", connection_id, dataset_id, webhook_token=auth_token_unauthorized
        )
        bad_request_response = {"statusCode": 400, "body": "Bad request"}
        forbidden_response = {"statusCode": 403, "body": "Forbidden"}

        assert connection_manager.handle(no_auth_event, {}) == bad_request_response
        assert connection_manager.handle(bearer_auth_event, {}) == forbidden_response
        assert connection_manager.handle(webhook_auth_event, {}) == forbidden_response

    def test_connect_unauthorized(self, mock_auth, mock_dynamodb):
        event = connection_event(
            "CONNECT", connection_id, dataset_id, bearer_token=auth_token_bad
        )
        assert connection_manager.handle(event, {}) == {
            "statusCode": 401,
            "body": "Unauthorized",
        }

    def test_disconnect_ok(self, mock_auth, mock_dynamodb):
        connected_client_item = {
            "connection_id": connection_id,
            "dataset_id": dataset_id,
            "connected_at": datetime_now,
        }
        table = create_subscriptions_table(items=[connected_client_item])

        response = connection_manager.handle(
            connection_event("DISCONNECT", connection_id, dataset_id), {}
        )

        assert connection_id not in [c["connection_id"] for c in table.scan()["Items"]]
        assert response["statusCode"] == 200
        assert response["body"] == "Disconnected"

    def test_unknown_event_type(self, mock_dynamodb):
        assert connection_manager.handle(
            connection_event("UNKNOWN", connection_id, dataset_id), {}
        ) == {"statusCode": 500, "body": "Unrecognized event type"}
