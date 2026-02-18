from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.queue import QueueMessage
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


@pytest.fixture
def azure_queue_message_factory():
    def _create_message(
        content: str = "test message content",
        dequeue_count: int = 1,
        message_id: str = "test-message-id",
        pop_receipt: str = "test-pop-receipt",
        inserted_on: datetime = None,
        expires_on: datetime = None,
        next_visible_on: datetime = None,
    ):
        message = QueueMessage(
            content=content,
            id=message_id,
            dequeue_count=dequeue_count,
            pop_receipt=pop_receipt,
            inserted_on=inserted_on or datetime.now(timezone.utc),
            expires_on=expires_on,
            next_visible_on=next_visible_on,
        )
        return message

    return _create_message


@pytest.fixture(autouse=True)
def mocked_create_storage_account_temp_url():
    with patch("zip_consumer.queue_zip_consumer.create_storage_account_temp_url") as mock:
        mock.return_value = "http://localhost:10000/devstoreaccount1/container/blob?mock_sas_token"
        yield mock
