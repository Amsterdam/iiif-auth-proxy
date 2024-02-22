import logging

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential, WorkloadIdentityCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient, QueueServiceClient
from django.conf import settings

log = logging.getLogger(__name__)

def get_queue_client():
    if settings.AZURITE_QUEUE_CONNECTION_STRING:
        queue_service_client = QueueServiceClient.from_connection_string(settings.AZURITE_QUEUE_CONNECTION_STRING)
        queue_client = queue_service_client.get_queue_client(settings.ZIP_QUEUE_NAME)
    else:
        credentials = WorkloadIdentityCredential()
        queue_client = QueueClient(credential=credentials, account_url=settings.QUEUE_ACCOUNT_URL, queue_name=settings.ZIP_QUEUE_NAME)
    
    # TODO: Move this into a Django migration so that it isn't run on every call to the queue
    try:
        queue_client.create_queue()
    except ResourceExistsError:
        pass
    
    return queue_client


def get_blob_service_client():
    if settings.AZURITE_STORAGE_CONNECTION_STRING:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURITE_STORAGE_CONNECTION_STRING)
    else:
        default_credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(settings.STORAGE_ACCOUNT_URL, credential=default_credential)
    return blob_service_client


def get_container_client(container_name):
    blob_service_client = get_blob_service_client()

    # TODO: Move this into a Django migration so that it isn't run on every call to the storage account
    try:
        container_client = blob_service_client.create_container(container_name)
    except ResourceExistsError:
        pass

    container_client = blob_service_client.get_container_client(container=container_name)
    return container_client


def get_blob_client(container_name, blob_name):
    blob_service_client = get_blob_service_client()
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    return blob_client


def store_object_on_storage_account(local_zip_file_path, filename):
    blob_client = get_blob_client(settings.STORAGE_ACCOUNT_CONTAINER_NAME, filename)
    with open(file=local_zip_file_path, mode="rb") as data:
        blob_client.upload_blob(data)
    return blob_client


def create_storage_account_temp_url(blob_client, expiry_days=0, expiry_hours=0, expiry_minutes=0):
    # TODO: Implement this
    pass
    

def remove_old_zips_from_storage_account(logger=None):
    # TODO: Implement this
    pass
