import logging
from datetime import datetime, timedelta

from azure.identity import DefaultAzureCredential, WorkloadIdentityCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
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


def create_storage_account_temp_url(blob_client, expiry_days=0):
    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        account_key=settings.STORAGE_ACCOUNT_ACCESS_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=expiry_days)
    )

    return f"{blob_client.url}?{sas_token}"


def remove_old_zips_from_storage_account():
    # TODO: Implement this
    pass
