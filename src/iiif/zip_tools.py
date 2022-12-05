import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from django.conf import settings
from ingress.models import Collection, Message

TMP_BOUWDOSSIER_ZIP_FOLDER = '/tmp/bouwdossier-zips/'


def store_zip_job(zip_info):
    # There's a lot of things in the request_meta that is not JSON serializable.
    # Since we just need some headers we simply remove all values that are not strings
    zip_info['request_meta'] = {k: v for k, v in zip_info['request_meta'].items() if type(v) is str}

    collection = Collection.objects.get(name=settings.ZIP_COLLECTION_NAME)
    message = Message.objects.create(
        raw_data=json.dumps(zip_info),
        collection=collection
    )
    return message


def create_tmp_folder():
    os.makedirs(TMP_BOUWDOSSIER_ZIP_FOLDER, exist_ok=True)
    zipjob_uuid = uuid4()
    tmp_folder_path = os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, str(zipjob_uuid))
    os.mkdir(tmp_folder_path)
    return zipjob_uuid, tmp_folder_path


def save_file_to_folder(folder, filename, content):
    file_path = os.path.join(folder, filename)
    open_mode = 'w' if isinstance(content, str) else 'wb'
    with open(file_path, open_mode) as f:
        f.write(content)

def create_local_zip_file(zipjob_uuid, folder_path):
    zip_file_path = os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, f'{zipjob_uuid}.zip')
    with ZipFile(zip_file_path, 'w') as zip_obj:
        for file in Path(folder_path).glob("*"):
            zip_obj.write(file, arcname=os.path.join(str(zipjob_uuid), file.name))
    return zip_file_path


def cleanup_local_files(zip_file_path, tmp_folder_path):
    # Cleanup the local zip file and folder with images
    os.remove(zip_file_path)
    shutil.rmtree(tmp_folder_path)
