import logging

from azure.identity import WorkloadIdentityCredential
from azure.storage.queue import QueueClient, QueueServiceClient
from django.conf import settings

log = logging.getLogger(__name__)


def get_queue_client():
    if settings.AZURITE_QUEUE_CONNECTION_STRING:
        queue_service_client = QueueServiceClient.from_connection_string(settings.AZURITE_QUEUE_CONNECTION_STRING)
        queue_client = queue_service_client.get_queue_client(settings.ZIP_QUEUE_NAME)
    else:
        credentials = WorkloadIdentityCredential()
        queue_client = QueueClient(
            credential=credentials,
            account_url=settings.QUEUE_ACCOUNT_URL,
            queue_name=settings.ZIP_QUEUE_NAME,
        )

    return queue_client
