# pip install azure-identity
# pip install azure-storage-queue
import errno
import functools
import logging
import os
import signal
import time

from azure.core.exceptions import ResourceExistsError

# use azure workload identity to login to queue
from azure.identity import DefaultAzureCredential, WorkloadIdentityCredential
from azure.storage.queue import QueueClient, QueueServiceClient

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "queue"
ACCOUNT_URL = "https://bouwdossiersdataoi5sk6et.queue.core.windows.net"
MESSAGE_VISIBILITY_TIMEOUT = 60

credentials = WorkloadIdentityCredential()
queue_client = QueueClient(
    credential=credentials, account_url=ACCOUNT_URL, queue_name=QUEUE_NAME
)
MESSAGE = "HOI KRIS, GROETJES UIT AKS"


def send_messages():
    queue_client.send_message("First message: " + MESSAGE)
    queue_client.send_message("Second message: " + MESSAGE)
    queue_client.send_message("Third message: " + MESSAGE)


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
        logger.info("Processing message: " + message.content)

    def get_queue_length(self):
        properties = queue_client.get_queue_properties()
        count = properties.approximate_message_count
        logger.info("Message count: " + str(count))
        return count


if __name__ == "__main__":
    send_messages()

    # consumer = AzureQueueConsumer()
    # consumer.run()
