from aws_lambda_powertools import Logger
import boto3
import re
import os

logger = Logger(service="sample")

# DICT = {}

# logger.info("causing an exception at import", dead_letter_queue=False)
# DICT["does_not_exist"]  # intentionally raise a KeyError at import

dead_letter_arn_re = re.compile(r'"deadLetterTargetArn":\s*"([^"]*)"')
RETRY_COUNT_MSG_ATTR = "SQSLambdaRetryCount"
_max_message_retries = int(os.environ.get("SQS_LAMBDA_RETRIES", "5"))
_backoff_initial_delay = int(os.environ.get("SQS_LAMBDA_BACKOFF_DELAY", "2"))
sqs_cli = boto3.client('sqs')


def get_retry_count(record):
    if "attributes" not in record:
        raise Exception("unexpected: no attribute for SQS message")

    attr = record["messageAttributes"]
    retry_attr = attr.get(RETRY_COUNT_MSG_ATTR, None)
    logger.info(f"attributes: {attr}")

    if retry_attr is None:
        return 0

    return int(retry_attr.get("stringValue"))


def get_remaining_retries(record):
    return _max_message_retries - get_retry_count(record)


def lambda_handler(event, context):
    records = event["Records"]
    logger.info(f"records: {records}")
    retry_queue_arn = records[0].get("eventSourceARN")
    retry_queue_name = retry_queue_arn[retry_queue_arn.rfind(":") + 1:]

    resp = sqs_cli.get_queue_url(QueueName=retry_queue_name)
    retry_queue_url = resp["QueueUrl"]
    logger.info(f"retry_queue_url: {retry_queue_url}")

    resp = sqs_cli.get_queue_attributes(QueueUrl=retry_queue_url,
                                        AttributeNames=["RedrivePolicy"])
    if "Attributes" not in resp and "RedrivePolicy" not in resp["Attributes"]:
        logger.info("unexpected: no redrive policy")
        return False

    redrive_policy = resp["Attributes"]["RedrivePolicy"]
    dead_letter_arn = dead_letter_arn_re.search(redrive_policy).group(1)
    if dead_letter_arn is None:
        logger.info("unexpected: no DLQ arn")
        return False

    dead_letter_queue_name = dead_letter_arn[dead_letter_arn.rfind(":") + 1:]
    resp = sqs_cli.get_queue_url(QueueName=dead_letter_queue_name)
    dead_letter_queue_url = resp["QueueUrl"]
    logger.info(f"dead_letter_queue_url: {dead_letter_queue_url}")

    for rec in records:
        retry_count = get_retry_count(rec)
        remaining_retries = get_remaining_retries(rec)
        if remaining_retries:
            retry_delay = _backoff_initial_delay * 2**retry_count
            retry_count += 1
            new_attr = rec["messageAttributes"].copy()
            new_attr[RETRY_COUNT_MSG_ATTR] = {
                "DataType": "Number",
                "StringValue": str(retry_count)
            }
            resp = sqs_cli.send_message(
                QueueUrl=retry_queue_url,
                DelaySeconds=retry_delay,
                MessageBody=rec["body"],
                MessageAttributes=new_attr
            )
            msg_id = resp["MessageId"]
            logger.info(f"delivered retry #{retry_count} to {retry_queue_url} as {msg_id}")
        else:
            new_attr = rec["messageAttributes"].copy()
            new_attr[RETRY_COUNT_MSG_ATTR] = {
                "DataType": "Number",
                "StringValue": str(retry_count)
            }
            resp = sqs_cli.send_message(
                QueueUrl=dead_letter_queue_url,
                MessageBody=rec["body"],
                MessageAttributes=new_attr
            )
            msg_id = resp["MessageId"]
            logger.info(f"Delivered error at retry #{retry_count} to {dead_letter_queue_url} as {msg_id}")

    return True
