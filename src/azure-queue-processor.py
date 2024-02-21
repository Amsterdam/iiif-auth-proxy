# pip install azure-identity
# pip install azure-storage-queue
import errno
import functools
import json
import logging
import os
import signal
import time

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential, WorkloadIdentityCredential
from azure.storage.queue import QueueClient, QueueServiceClient

logging.basicConfig(level=logging.INFO)
# logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
#     logging.WARNING
# )
logger = logging.getLogger(__name__)

QUEUE_NAME = "zip-queue"
MESSAGE_VISIBILITY_TIMEOUT = 60

# # On Azure
# ACCOUNT_URL = "https://bouwdossiersdataoi5sk6et.queue.core.windows.net"
# credentials = WorkloadIdentityCredential()
# queue_client = QueueClient(
#     credential=credentials, account_url=ACCOUNT_URL, queue_name=QUEUE_NAME
# )

# Local with azurite
AZURITE_QUEUE_CONNECTION_STRING = 'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;'
queue_service_client = QueueServiceClient.from_connection_string(AZURITE_QUEUE_CONNECTION_STRING)
queue_client = queue_service_client.get_queue_client(QUEUE_NAME)


def send_messages():
    try:
        queue_client.create_queue()
    except ResourceExistsError as e:
        logger.error("Error creating queue: " + str(e))

    for i in range(3):
        queue_client.send_message(json.dumps({"my_message": f"Message {i}"}))
    

class TimeoutError(Exception):
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    """https://stackoverflow.com/questions/2281850/timeout-function-if-it-takes-too-long-to-finish"""

    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


class AzureQueueConsumer:
    MESSAGE_VISIBILITY_TIMEOUT = 30

    def run(self):
        while True:
            count = self.get_queue_length()
            if count == 0:
                time.sleep(5)
                continue
            message_iterator = queue_client.receive_messages(
                max_messages=1, visibility_timeout=MESSAGE_VISIBILITY_TIMEOUT
            )
            for message in message_iterator:
                self.process_message(message)
                queue_client.delete_message(message.id, message.pop_receipt)

    @timeout(MESSAGE_VISIBILITY_TIMEOUT)
    def process_message(self, message):
        """
        Be careful with the visibility timeout! If the message is still processing when the visibility timeout
        expires, the message will be put back on the queue and will be processed again. This can lead to duplicate
        messages!!! Always use a timeout decorator to prevent this.
        """
        logger.info(f"#################### Processing message (type {type(message.content)}): {message.content} ")
        content_dict = json.loads(message.content)
        logger.info(f"####################  {type(content_dict)} {content_dict}" )
        

    def get_queue_length(self):
        properties = queue_client.get_queue_properties()
        count = properties.approximate_message_count
        logger.info("#################### Message count: " + str(count))
        return count


if __name__ == "__main__":
    send_messages()

    consumer = AzureQueueConsumer()
    consumer.run()
