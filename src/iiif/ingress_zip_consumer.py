import json
import logging
import os

from django.conf import settings
from django.template.loader import render_to_string
from ingress.consumer.base import BaseConsumer

from iiif import authentication, image_server, mailing, object_store, tools, zip_tools
from iiif.metadata import get_metadata
from main import settings

log = logging.getLogger(__name__)


class ZipConsumer(BaseConsumer):
    collection_name = settings.ZIP_COLLECTION_NAME

    """
    Whether or not to immediately remove messages once consumption succeeds.
    If set to False, message.consume_succeeded_at will be set.
    """
    remove_message_on_consumed = False

    """
    Whether or not to set Message.consume_started_at immediately once consumption starts
    """
    set_consume_started_at = True

    def consume_raw_data(self, raw_data):
        log.info("Started consume_raw_data")
        try:
            record = json.loads(raw_data)

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
                except tools.ImmediateHttpResponse as e:
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

            # Move the file to the object store
            conn = object_store.get_object_store_connection()
            object_store.store_object_on_object_store(
                conn, zip_file_path, zip_file_name
            )

            # Create a temporary url
            temp_zip_download_url = object_store.create_object_store_temp_url(
                conn, zip_file_name, expiry_days=settings.TEMP_URL_EXPIRY_DAYS
            )

            # Send the email
            email_subject = "Downloadlink Bouw- en omgevingdossiers"
            email_body = render_to_string(
                "download_zip.html", {"temp_zip_download_url": temp_zip_download_url}
            )
            mailing.send_email(record["email_address"], email_subject, email_body)

            # Cleanup the local zip file and folder with images
            zip_tools.cleanup_local_files(zip_file_path, tmp_folder_path)

        except Exception as e:
            log.exception("ingress_zip_consumer_error:", e)
            raise e
