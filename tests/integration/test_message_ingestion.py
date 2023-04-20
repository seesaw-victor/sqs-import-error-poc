import json
import os

import boto3
import pytest
from aws_lambda_powertools.utilities.parameters import get_parameter
from mypy_boto3_sqs import SQSClient


@pytest.fixture
def stack_config():
    stage = os.getenv("STAGE", default="dev")
    resource_map_param = f"/{stage}/service/sqs_import_error_poc/test/config"
    cfg = get_parameter(name=resource_map_param)
    return json.loads(cfg)


@pytest.fixture
def queue_without_dlq(stack_config: dict):
    return stack_config["QueueWithoutDLQ"]

@pytest.fixture
def queue_with_dlq(stack_config: dict):
    return stack_config["QueueWithDLQ"]


def test_message_queue_no_dlq(queue_without_dlq: str):
    sqs: SQSClient = boto3.client("sqs")
    sqs.send_message(QueueUrl=queue_without_dlq, MessageBody='test')

def test_message_queue_with_dlq(queue_with_dlq: str):
    sqs: SQSClient = boto3.client("sqs")
    sqs.send_message(QueueUrl=queue_with_dlq, MessageBody='test')


