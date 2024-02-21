import json
import logging
import time
import os

import timeout_decorator
from django.conf import settings
from django.template.loader import render_to_string

from iiif import authentication, image_server, mailing, utils, zip_tools
from iiif.metadata import get_metadata
from iiif.utils_azure import get_queue_client
from main import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass


class AzureZipQueueConsumer:
    # Be careful with the visibility timeout! If the message is still processing when the visibility timeout
    # expires, the message will be put back on the queue and will be processed again. This can lead to duplicate
    # messages!!! Always use a timeout decorator to prevent this.
    # an hour, because some zips can simply be very very large
    MESSAGE_VISIBILITY_TIMEOUT = 3600

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
                message_iterator = [m for m in self.queue_client.receive_messages(messages_per_page=1, visibility_timeout=1)]
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
            record = json.loads(message.content)

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
                    record["request_meta"].get("HTTP_AUTHORIZATION"),
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
                    record["request_meta"],
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

            # TODO: ENABLE CODE BELOW
            # # Move the file to the object store
            # conn = object_store.get_object_store_connection()
            # object_store.store_object_on_object_store(
            #     conn, zip_file_path, zip_file_name
            # )
            # breakpoint()
            # # Create a temporary url
            # temp_zip_download_url = object_store.create_object_store_temp_url(
            #     conn, zip_file_name, expiry_days=settings.TEMP_URL_EXPIRY_DAYS
            # )
            # breakpoint()
            # # Send the email
            # email_subject = "Downloadlink Bouw- en omgevingdossiers"
            # email_body = render_to_string(
            #     "download_zip.html", {"temp_zip_download_url": temp_zip_download_url}
            # )
            # mailing.send_email(record["email_address"], email_subject, email_body)

            # Cleanup the local zip file and folder with images
            zip_tools.cleanup_local_files(zip_file_path, tmp_folder_path)

        except Exception as e:
            breakpoint()
            logger.exception("ingress_zip_consumer_error:", e)
            raise e
