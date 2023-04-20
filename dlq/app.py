from aws_lambda_powertools import Logger

logger = Logger(service="sample")

DICT = {}

logger.info("causing an exception at import", dead_letter_queue=False)
DICT["does_not_exist"]  # intentionally raise a KeyError at import


def lambda_handler(event, context):
    return True
