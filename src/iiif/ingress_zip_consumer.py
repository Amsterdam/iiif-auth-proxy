import json
import logging
import os

from django.conf import settings
from ingress.consumer.base import BaseConsumer

from iiif import tools
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
        record = json.loads(raw_data)

        # Create a tmp folder to store downloaded source files
        zipjob_uuid, tmp_folder_path = tools.create_tmp_folder()

        # Init contents of txt info file which is sent along in the zip
        info_txt_contents = "The following files were requested:\n"

        # Get all the source files and put them in a folder to be zipped afterwards
        for i, (iiif_url, info) in enumerate(record['urls'].items()):
            info_txt_contents += f"{iiif_url}: "
            try:
                file_response, file_url = tools.get_file(
                    record['request_meta'], info['url_info'], iiif_url, info['metadata'])
                tools.handle_file_response_errors(file_response, file_url)
            except tools.ImmediateHttpResponse as e:
                log.error(f"Error while retrieving {iiif_url} from the source system: {e.response.content}")
                info_txt_contents += f"Not included in this zip because an error occurred " \
                                     f"while getting it from the source system\n"
                continue
            except Exception as e:
                log.error(f"Error while retrieving {iiif_url} from the source system: {e}")
                info_txt_contents += f"Not included in this zip because an error occurred " \
                                     f"while getting it from the source system\n"
                continue

            # Save image file to tmp folder
            tools.save_file_to_folder(tmp_folder_path, info['url_info']['filename'], file_response.content)
            info_txt_contents += "included\n"

        # Store the info_file_along_with_the_image_files
        tools.save_file_to_folder(tmp_folder_path, 'report.txt', info_txt_contents)

        # Zip all files together
        zip_file_path = tools.create_local_zip_file(zipjob_uuid, tmp_folder_path)
        zip_file_name = os.path.basename(zip_file_path)

        # Move the file to the object store
        conn = tools.get_object_store_connection()
        tools.store_object_on_object_store(conn, zip_file_path, zip_file_name)

        # Create a temporary url
        temp_zip_download_url = tools.create_object_store_temp_url(
            conn,
            zip_file_name,
            expiry_days=settings.TEMP_URL_EXPIRY_DAYS)

        # Send the email
        # TODO: Make better texts and an email template for this email
        email_subject = "Your zip download is ready"
        email_body = f"The files you requested can be downloaded from this url: <a clicktracking=off href='{temp_zip_download_url}'>{temp_zip_download_url}</a>"
        tools.send_email(record['email_address'], email_subject, email_body)

        # Cleanup the local zip file and folder with images
        tools.cleanup_local_files(zip_file_path, tmp_folder_path)
