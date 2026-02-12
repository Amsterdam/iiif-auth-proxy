import json
import logging
import os
import time

import timeout_decorator
from django.conf import settings
from django.template.loader import render_to_string

from auth_mail import mailing
from core.auth.document_access import (
    file_can_be_zipped,
)
from iiif import image_server
from iiif.metadata import get_metadata
from utils.queue import get_queue_client
from utils.storage import (
    create_storage_account_temp_url,
    get_blob_from_storage_account,
    remove_blob_from_storage_account,
    store_file_on_storage_account,
)
from zip_consumer import zip_tools

logger = logging.getLogger(__name__)


class AzureZipQueueConsumer:
    # Be careful with the visibility timeout! If the message is still processing when the visibility timeout
    # expires, the message will be put back on the queue and will be processed again. This can lead to duplicate
    # messages!!! Always use a timeout decorator to prevent this.
    # We set it to an hour, because some zips can simply be very, very large
    MESSAGE_VISIBILITY_TIMEOUT = 3600

    # This consumer accepts messages with this name
    MESSAGE_VERSION_NAME = zip_tools.ZIP_MESSAGE_VERSION_NAME

    def __init__(self, end_at_empty_queue=False):
        self.queue_client = get_queue_client()
        self.end_at_empty_queue = end_at_empty_queue

    def get_queue_length(self):
        properties = self.queue_client.get_queue_properties()
        count = properties.approximate_message_count
        return count

    def run(self):
        while True:
            count = self.get_queue_length()
            message_iterator = None

            if self.end_at_empty_queue:
                # This part is only for testing purposes.
                # To be able to exit the running process when the queue is empty.
                message_iterator = list(self.queue_client.receive_messages(messages_per_page=10, visibility_timeout=5))
                if count == 0 or len(message_iterator) == 0:
                    break

            if count == 0:
                time.sleep(5)
                continue

            if message_iterator is None:
                message_iterator = self.queue_client.receive_messages(
                    max_messages=1, visibility_timeout=self.MESSAGE_VISIBILITY_TIMEOUT
                )

            for message in message_iterator:
                try:
                    self.process_message(message)
                except Exception as e:
                    _job_content = json.loads(message.content)
                    logger.error(
                        f"An exception occurred during processing of message data uuid {_job_content['data']}: {e}"
                    )
                    if message.dequeue_count > 5:
                        logger.info(f"Deleting the message, dequeue count is too high. {message.dequeue_count=}")
                        self.queue_client.delete_message(message.id, message.pop_receipt)
                else:
                    self.queue_client.delete_message(message.id, message.pop_receipt)

    @timeout_decorator.timeout(MESSAGE_VISIBILITY_TIMEOUT)
    def process_message(self, message):

        logger.info("Started process_message")

        if message.dequeue_count > 5:
            logger.info(f"Skipping the message, dequeue count is too high. {message.dequeue_count=}")
            return

        job = json.loads(message.content)
        if not job["version"] == self.MESSAGE_VERSION_NAME:
            return

        # Get the job from the storage account
        job_blob_name = job["data"]
        blob_client, blob = get_blob_from_storage_account(
            settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME, job_blob_name
        )
        record = json.loads(blob)

        # Prepare folder and report.txt file for downloads
        (
            zipjob_uuid,
            tmp_folder_path,
            info_txt_contents,
        ) = image_server.prepare_zip_downloads()

        # Get metadata and files from image servers
        metadata_cache = {}
        for iiif_url, image_info in record["urls"].items():
            metadata, metadata_cache = get_metadata(
                image_info["url_info"],
                iiif_url,
                metadata_cache,
            )

            can_be_zipped, fail_reason = file_can_be_zipped(metadata, image_info["url_info"], record["scope"])

            info_txt_contents = image_server.download_file_for_zip(
                iiif_url,
                info_txt_contents,
                image_info["url_info"],
                fail_reason,
                metadata,
                tmp_folder_path,
            )
        # Store the info_file_along_with_the_image_files
        zip_tools.save_file_to_folder(tmp_folder_path, "report.txt", info_txt_contents)

        # Zip all files together
        zip_file_path = zip_tools.create_local_zip_file(zipjob_uuid, tmp_folder_path)
        zip_file_name = os.path.basename(zip_file_path)

        blob_client, blob_service_client = store_file_on_storage_account(
            settings.STORAGE_ACCOUNT_CONTAINER_NAME, zip_file_path, zip_file_name
        )

        temp_zip_download_url = create_storage_account_temp_url(blob_client, blob_service_client)

        email_subject = "Downloadlink Bouw- en omgevingdossiers"
        email_body = render_to_string("download_zip.html", {"temp_zip_download_url": temp_zip_download_url})

        mailing.send_email(record["email_address"], email_subject, email_body)

        remove_blob_from_storage_account(settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME, job_blob_name)
        zip_tools.cleanup_local_files(zip_file_path, tmp_folder_path)
