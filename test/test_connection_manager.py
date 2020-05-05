from aws_xray_sdk.core import xray_recorder

xray_recorder.begin_segment("Test")


class TestConnectionManager:
    def test_get_boilerplate(self):
        assert True
