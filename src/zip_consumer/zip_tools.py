import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from main.utils_azure_storage import get_queue_client

TMP_BOUWDOSSIER_ZIP_FOLDER = "/tmp/bouwdossier-zips/"
ZIP_MESSAGE_VERSION_NAME = "zip_job_v1"


def store_zip_job(job_name):
    zip_job = json.dumps(
        {
            "version": ZIP_MESSAGE_VERSION_NAME,
            "data": job_name,
        }
    )

    queue_client = get_queue_client()
    queue_client.send_message(zip_job)


def create_tmp_folder():
    os.makedirs(TMP_BOUWDOSSIER_ZIP_FOLDER, exist_ok=True)
    zipjob_uuid = str(uuid4())
    tmp_folder_path = os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, zipjob_uuid)
    os.mkdir(tmp_folder_path)
    return zipjob_uuid, tmp_folder_path


def save_file_to_folder(folder, filename, content):
    file_path = os.path.join(folder, filename)
    open_mode = "w" if isinstance(content, str) else "wb"
    with open(file_path, open_mode) as f:
        f.write(content)


def create_local_zip_file(zipjob_uuid, folder_path):
    zip_file_path = os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, f"{zipjob_uuid}.zip")
    with ZipFile(zip_file_path, "w") as zip_obj:
        for file in Path(folder_path).glob("*"):
            zip_obj.write(file, arcname=os.path.join(zipjob_uuid, file.name))
    return zip_file_path


def cleanup_local_files(zip_file_path, tmp_folder_path):
    # Cleanup the local zip file and folder with images
    os.remove(zip_file_path)
    shutil.rmtree(tmp_folder_path)
