import json
import logging
import os
import time

import timeout_decorator
from django.conf import settings
from django.template.loader import render_to_string

from iiif import authentication, image_server, mailing, utils, zip_tools
from iiif.metadata import get_metadata
from iiif.utils_azure import (
    create_storage_account_temp_url,
    get_blob_from_storage_account,
    get_queue_client,
    remove_blob_from_storage_account,
    store_file_on_storage_account,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    pass


class AzureZipQueueConsumer:
    # Be careful with the visibility timeout! If the message is still processing when the visibility timeout
    # expires, the message will be put back on the queue and will be processed again. This can lead to duplicate
    # messages!!! Always use a timeout decorator to prevent this.
    # We set it to an hour, because some zips can simply be very very large
    MESSAGE_VISIBILITY_TIMEOUT = 3600

    # This consumer accepts messages with this name
    MESSAGE_VERSION_NAME = "zip_job_v1"

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
                # This part is only for testing purposes. To be able to exit the running process when the queue is empty.
                message_iterator = [
                    m
                    for m in self.queue_client.receive_messages(
                        messages_per_page=10, visibility_timeout=5
                    )
                ]
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
                self.process_message(message)
                self.queue_client.delete_message(message.id, message.pop_receipt)

    @timeout_decorator.timeout(MESSAGE_VISIBILITY_TIMEOUT)
    def process_message(self, message):

        logger.info("Started process_message")
        try:
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
                fail_reason = None
                metadata, metadata_cache = get_metadata(
                    image_info["url_info"],
                    iiif_url,
                    metadata_cache,
                )
                try:
                    authentication.check_file_access_in_metadata(
                        metadata, image_info["url_info"], record["scope"]
                    )
                    authentication.check_restricted_file(
                        metadata, image_info["url_info"]
                    )
                except utils.ImmediateHttpResponse as e:
                    fail_reason = e.response.content.decode("utf-8")

                info_txt_contents = image_server.download_file_for_zip(
                    iiif_url,
                    info_txt_contents,
                    image_info["url_info"],
                    fail_reason,
                    metadata,
                    None,  # TODO: Remove parameter because not needed anymore (was: record["request_meta"])
                    tmp_folder_path,
                )
            # Store the info_file_along_with_the_image_files
            zip_tools.save_file_to_folder(
                tmp_folder_path, "report.txt", info_txt_contents
            )

            # Zip all files together
            zip_file_path = zip_tools.create_local_zip_file(
                zipjob_uuid, tmp_folder_path
            )
            zip_file_name = os.path.basename(zip_file_path)

            blob_client, blob_service_client = store_file_on_storage_account(
                settings.STORAGE_ACCOUNT_CONTAINER_NAME, zip_file_path, zip_file_name
            )

            temp_zip_download_url = create_storage_account_temp_url(
                blob_client, blob_service_client
            )

            email_subject = "Downloadlink Bouw- en omgevingdossiers"
            email_body = render_to_string(
                "download_zip.html", {"temp_zip_download_url": temp_zip_download_url}
            )

            mailing.send_email(record["email_address"], email_subject, email_body)

            remove_blob_from_storage_account(
                settings.STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME, job_blob_name
            )
            zip_tools.cleanup_local_files(zip_file_path, tmp_folder_path)

        except Exception as e:
            logger.exception("queue_zip_consumer_error:", e)
            raise e
