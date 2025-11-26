import logging
from datetime import datetime, timedelta

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
from django.conf import settings

log = logging.getLogger(__name__)


def get_blob_service_client():
    if settings.AZURITE_STORAGE_CONNECTION_STRING:
        # TODO: Move this code to a mocking of this function in the tests
        blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURITE_STORAGE_CONNECTION_STRING
        )
    else:
        default_credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(
            settings.STORAGE_ACCOUNT_URL, credential=default_credential
        )
    return blob_service_client


def get_container_client(container_name):
    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(
        container=container_name
    )
    return container_client


def get_blob_client(container_name, blob_name):
    blob_service_client = get_blob_service_client()
    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=blob_name
    )
    return blob_client, blob_service_client


def store_file_on_storage_account(storage_container, local_file_path, blob_name):
    blob_client, blob_service_client = get_blob_client(storage_container, blob_name)
    with open(file=local_file_path, mode="rb") as data:
        blob_client.upload_blob(data)
    return blob_client, blob_service_client


def store_blob_on_storage_account(storage_container, blob_name, blob):
    blob_client, blob_service_client = get_blob_client(
        container_name=storage_container, blob_name=blob_name
    )
    blob_client.upload_blob(blob, overwrite=True)
    return blob_client, blob_service_client


def get_blob_from_storage_account(storage_container, blob_name):
    blob_client, _ = get_blob_client(
        container_name=storage_container, blob_name=blob_name
    )
    blob = blob_client.download_blob().readall()
    return blob_client, blob


def remove_blob_from_storage_account(storage_container, blob_name):
    blob_client, _ = get_blob_client(
        container_name=storage_container, blob_name=blob_name
    )
    blob_client.delete_blob()


def create_storage_account_temp_url(
    blob_client, blob_service_client, expiry_days=settings.TEMP_URL_EXPIRY_DAYS
):
    key_start_time = datetime.utcnow()
    key_expiry_time = key_start_time + timedelta(days=expiry_days)
    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time, key_expiry_time
    )

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        account_key=user_delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=expiry_days),
    )

    file_url = blob_client.url.replace(blob_service_client.url, settings.APP_BASE_URL)

    return f"{file_url}?{sas_token}"
