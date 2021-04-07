import json

from ingress.consumer.base import BaseConsumer

from iiif import mailing
from main import settings


class EmailConsumer(BaseConsumer):
    collection_name = settings.EMAIL_COLLECTION_NAME

    """
    Whether or not to immediately remove messages once consumption succeeds.
    If set to False, message.consume_succeeded_at will be set.
    """
    remove_message_on_consumed = True

    """
    Whether or not to set Message.consume_started_at immediately once consumption starts
    """
    set_consume_started_at = False

    def consume_raw_data(self, raw_data):
        record = json.loads(raw_data)
        mailing.send_email(record['email'], record['subject'], record['body'])
