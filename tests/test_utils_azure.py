from pathlib import Path
from uuid import uuid4

import requests
from azure.core.exceptions import ResourceExistsError
from django.conf import settings

from iiif.utils_azure import get_blob_service_client, get_queue_client


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
