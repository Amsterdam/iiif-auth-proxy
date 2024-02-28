from pathlib import Path
from uuid import uuid4

import requests
from azure.core.exceptions import ResourceExistsError
from django.conf import settings

from iiif.utils_azure import (
    create_storage_account_temp_url,
    get_blob_service_client,
    get_queue_client,
    store_object_on_storage_account,
)


def create_blob_container(container_name):
    blob_service_client = get_blob_service_client()
    try:
        container_client = blob_service_client.create_container(container_name, public_access=None)
    except ResourceExistsError:
        pass
    container_client = blob_service_client.get_container_client(container=container_name)
    return container_client

def create_queue():
    queue_client = get_queue_client()    
    try:
        queue_client.create_queue()
    except ResourceExistsError:
        pass


class TestUtils:
    def setup_method(self):
        create_blob_container(settings.STORAGE_ACCOUNT_CONTAINER_NAME)
        create_queue()

    def test_create_blob_temp_url(self):
        # Create file with random content in /tmp/
        file_path = Path("/tmp") / f"{uuid4()}.txt"
        file_path.write_text("This is a test file")

        # Store file on storage account
        blob_client = store_object_on_storage_account(file_path, file_path.name)

        # Create temporary URL
        temp_url = create_storage_account_temp_url(blob_client, expiry_days=1)
        
        r = requests.get(temp_url)
        assert r.status_code == 200

