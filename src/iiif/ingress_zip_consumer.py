import json
import logging
import os

from django.conf import settings
from django.template.loader import render_to_string
from ingress.consumer.base import BaseConsumer

from iiif import cantaloupe, mailing, object_store, zip_tools
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

            # Download all the files from the source systems through cantaloupe
            tmp_folder_path, info_txt_contents, zipjob_uuid = cantaloupe.download_files_for_zip(record)

            # Store the info_file_along_with_the_image_files
            zip_tools.save_file_to_folder(tmp_folder_path, 'report.txt', info_txt_contents)

            # Zip all files together
            zip_file_path = zip_tools.create_local_zip_file(zipjob_uuid, tmp_folder_path)
            zip_file_name = os.path.basename(zip_file_path)

            # Move the file to the object store
            conn = object_store.get_object_store_connection()
            object_store.store_object_on_object_store(conn, zip_file_path, zip_file_name)

            # Create a temporary url
            temp_zip_download_url = object_store.create_object_store_temp_url(
                conn,
                zip_file_name,
                expiry_days=settings.TEMP_URL_EXPIRY_DAYS)

            # Send the email
            email_subject = "Downloadlink Bouw- en omgevingdossiers"
            email_body = render_to_string('download_zip.html', {'temp_zip_download_url': temp_zip_download_url})
            mailing.send_email(record['email_address'], email_subject, email_body)

            # Cleanup the local zip file and folder with images
            zip_tools.cleanup_local_files(zip_file_path, tmp_folder_path)

        except Exception as e:
            log.error("ingress_zip_consumer_error:", e)
            raise e
