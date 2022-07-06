import hmac
import logging
import os
from datetime import datetime
from hashlib import sha1
from time import time

from django.conf import settings
from swiftclient import Connection
from swiftclient.exceptions import ClientException
from swiftclient.service import SwiftError, SwiftService, SwiftUploadObject

log = logging.getLogger(__name__)


def get_object_store_connection():
    return Connection(**settings.OBJECT_STORE)


def store_small_object_on_object_store(connection, local_zip_file_path, filename):
    with open(local_zip_file_path, 'rb') as local:
        connection.put_object(
            settings.OBJECT_STORE_CONTAINER_NAME,
            filename,
            contents=local,
            content_type='application/zip'
        )


def store_large_object_on_object_store(local_zip_file_path, filename):
    _opts = {'object_dd_threads': 20, 'segment_size': 262144000, 'use_slo': True}
    with SwiftService(options=_opts) as swift:
        try:
            container = settings.OBJECT_STORE_CONTAINER_NAME
            objects = [SwiftUploadObject(local_zip_file_path, object_name=filename)]
            for r in swift.upload(container=container, objects=objects):
                if r['success']:
                    if 'for_object' in r:
                        continue
                    elif 'object' in r:
                        return
                else:
                    if r['action'] == "create_container":
                        log.warning(
                            f"Warning: failed to create container {container} {r['error']}"
                        )
                    elif r['action'] == "upload_object":
                        log.error(
                            f"Failed to upload object %s to container {container}: {r['object']}, {r['error']}"
                        )
                    else:
                        log.error(r['error'])
        except SwiftError as e:
            log.error(e.value)


def store_object_on_object_store(connection, local_zip_file_path, filename):
    file_size = os.path.getsize(local_zip_file_path)
    if file_size < 5368709120:  # 5GB
        store_small_object_on_object_store(connection, local_zip_file_path, filename)
    else:
        store_large_object_on_object_store(local_zip_file_path, filename)


def create_object_store_temp_url(connection, file_name, expiry_minutes=0, expiry_hours=0, expiry_days=0):
    # Create signature body
    method = 'GET'
    duration_in_seconds = ((((expiry_days * 24) + expiry_hours) * 60) + expiry_minutes) * 60
    expires = int(time() + duration_in_seconds)
    path = os.path.join(f'/{settings.OBJECT_STORE_CONTAINER_NAME}', file_name)
    hmac_body = f'{method}\n{expires}\n{path}'.encode('utf-8')

    # Create signature
    key = bytes(settings.OBJECT_STORE_TEMP_URL_KEY, 'UTF-8')
    sig = hmac.new(key, hmac_body, sha1).hexdigest()

    # Create url
    tenant_id = connection.os_options['tenant_id']
    url = f'https://{tenant_id}.{settings.OBJECT_STORE_TLD}{path}?temp_url_sig={sig}&temp_url_expires={expires}'

    return url


def remove_old_zips_from_object_store(logger=None):
    if logger is None:
        logger = log

    conn = get_object_store_connection()

    # Get list of files from the object store
    headers, files = conn.get_container(settings.OBJECT_STORE_CONTAINER_NAME)
    logger.info(f"Checking {headers['x-container-object-count']} files for removal")

    # Loop over files on object store and remove the old ones
    removed_counter = 0
    failed_counter = 0
    for file in files:
        file_age = datetime.now() - datetime.fromisoformat(file['last_modified'])
        if file_age.days > settings.TEMP_URL_EXPIRY_DAYS:
            try:
                conn.delete_object(settings.OBJECT_STORE_CONTAINER_NAME, file['name'])
                logger.info(f"Removed {file['name']}")
                removed_counter += 1
            except ClientException as e:
                logger.error(f"Failed to remove {file['name']} with error: {e}")
                failed_counter += 1

    logger.info(f"\nSuccessfully removed {removed_counter} old files from the object store.\n")
    if failed_counter:
        logger.info(f"\nFAILED removing {failed_counter} old files from the object store.\n")
