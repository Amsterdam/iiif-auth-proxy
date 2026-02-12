from contextlib import contextmanager

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from django.conf import settings

from utils.queue import get_queue_client
from utils.storage import get_blob_service_client


@contextmanager
def blob_container(container_name: str):
    blob_service_client = get_blob_service_client()

    try:
        blob_service_client.create_container(container_name, public_access=None)
    except ResourceExistsError:
        pass

    container_client = blob_service_client.get_container_client(container_name)

    try:
        yield container_client
    finally:
        try:
            container_client.delete_container()
        except ResourceNotFoundError:
            pass


@pytest.fixture(scope="session", autouse=True)
def download_blob_container():
    with blob_container(settings.STORAGE_ACCOUNT_CONTAINER_NAME) as container:
        yield container


@pytest.fixture(scope="session", autouse=True)
def zip_jobs_blob_container():
    with blob_container(settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME) as container:
        yield container


@pytest.fixture(scope="session", autouse=True)
def test_queue_client():
    queue_client = get_queue_client()

    try:
        queue_client.create_queue()
    except ResourceExistsError:
        pass

    # Make sure the queue is empty
    queue_client.clear_messages()

    yield queue_client

    try:
        queue_client.delete_queue()
    except ResourceNotFoundError:
        pass
