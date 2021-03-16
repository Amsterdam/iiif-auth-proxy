import hmac
import json
import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from hashlib import sha1
from pathlib import Path
from time import time
from uuid import uuid4
from zipfile import ZipFile

import jwt
import requests
import sendgrid
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed
from ingress.models import Collection, Message
from jwt.exceptions import (DecodeError, ExpiredSignatureError,
                            InvalidSignatureError)
from requests.exceptions import RequestException
from sendgrid.helpers.mail import Mail
from swiftclient import Connection
from swiftclient.exceptions import ClientException

log = logging.getLogger(__name__)


RESPONSE_CONTENT_NO_TOKEN = "No token supplied"
RESPONSE_CONTENT_INVALID_SCOPE = "Invalid scope"
RESPONSE_CONTENT_JWT_TOKEN_EXPIRED = "Your token has expired. Request a new token."
RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA = "Document not found in metadata"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER = "The iiif-metadata-server cannot be reached"
RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE = "The iiif-image-server cannot be reached"
RESPONSE_CONTENT_COPYRIGHT = "Document has copyright restriction"
RESPONSE_CONTENT_RESTRICTED = "Document access is restricted"



class InvalidIIIFUrlError(Exception):
    pass


class DocumentNotFoundInMetadataError(Exception):
    pass


class ImmediateHttpResponse(Exception):
    """
    This exception is used to interrupt the flow of processing to immediately
    return a custom HttpResponse.
    """
    _response = HttpResponse("Nothing provided.")

    def __init__(self, response):
        self._response = response

    @property
    def response(self):
        return self._response


def get_meta_data(url_info):
    # Test with:
    # curl -i -H "Accept: application/json" http://iiif-metadata-server-api.service.consul:8183/iiif-metadata/bouwdossier/SA85385/
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}{url_info['dossier']}/"
    return requests.get(metadata_url)


def create_wabo_url(url_info, metadata):
    for document in metadata['documenten']:
        if document['barcode'] == url_info['document_barcode']:
            filename = document['bestanden'][0]['filename']
            if url_info['source_file']:
                # This means that in order to avoid any file conversions we're bypassing cantaloupe
                # and going directly to the source server to get the raw file and serve that
                return f"{filename}"
            else:
                return f"2/{url_info['source']}:{filename.replace('/', '-')}/{url_info['formatting']}"
    # TODO: raise something in the unlikely event that nothing is found


# TODO: split into two functions, one for url and one for headers
def create_file_url_and_headers(request_meta, url_info, iiif_url, metadata):
    iiif_url = iiif_url.replace(' ', '%20')
    headers = {}
    if 'HTTP_X_FORWARDED_PROTO' in request_meta and 'HTTP_X_FORWARDED_HOST' in request_meta:
        # Make sure the iiif-image-server gets the protocol and the host of the initial request so that
        # any other info urls in the response have the correct public url, instead of the
        # local .service.consul url.
        headers['X-Forwarded-Proto'] = request_meta['HTTP_X_FORWARDED_PROTO']
        headers['X-Forwarded-Host'] = request_meta['HTTP_X_FORWARDED_HOST']
    else:
        # Added for local testing. If X-Forwarded-ID is present the iiif imageserver
        # also needs to have the X-Forwarded-Host and or X-Forwarded-Port
        # Otherwise the X-Forwarded-Id is used by iiif image server in the destination URI
        http_host = request_meta.get("HTTP_HOST","").split(':')
        if len(http_host) >= 2:
            headers['X-Forwarded-Host'] = http_host[0]
            headers['X-Forwarded-Port'] = http_host[1]

    if url_info['source'] == 'edepot':
        # If the iiif url contains a reference to dossier like SQ1421 without - then
        # this was added to ad reference to stadsdeel and dossiernumber and it should be removed
        iiif_url_edepot = re.sub(r":[A-Z]+\d+-", ":", iiif_url)
        if iiif_url_edepot != iiif_url:
            headers['X-Forwarded-ID'] = iiif_url.split('/')[1]
        iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{iiif_url_edepot}"
        return iiif_image_url, headers, ()
    elif url_info['source'] == 'wabo':
        if url_info['source_file'] == True:
            # This means that in order to avoid any file conversions we're bypassing cantaloupe
            # and going directly to the source server to get the raw file and serve that
            wabo_url = create_wabo_url(url_info, metadata)
            iiif_image_url = f"{settings.WABO_BASE_URL}{wabo_url}"
            cert = '/tmp/sw444v1912.pem'
            return iiif_image_url, headers, cert
        else:
            headers['X-Forwarded-ID'] = iiif_url.split('/')[1]
            wabo_url = create_wabo_url(url_info, metadata)
            iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{wabo_url}"
            return iiif_image_url, headers, ()


def get_image_from_iiif_server(file_url, headers, cert):
    return requests.get(file_url, headers=headers, cert=cert)


def get_info_from_iiif_url(iiif_url, source_file):
    ## PRE-WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST-00015-ST00000126_00001.jpg=filename  ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand

    ## WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547/full/full/0/default.jpg""
    # SDZ-38657-4900487_628547=filename  SDZ=stadsdeel  38657=dossier  4900487=olo_liaan_nummer  628547=document_barcode

    # At the end of the url, this can be appended '?source_file=true', which means we'll bypass
    # cantaloupe and go directly for the source file

    try:
        source = iiif_url.split(':')[0].split('/')[1]  # "edepot" or "wabo"
        relevant_url_part = iiif_url.split(':')[1].split('/')[0]
        formatting = iiif_url.split(':')[1].split('/', 1)[1].split('?')[0] if '/' in iiif_url.split(':')[1] else ''

        if source == 'edepot':  # == pre-wabo
            m = re.match(r"^([A-Z]+)-?(\d+)-(.+)$", relevant_url_part)
            if not m:
                raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")
            stadsdeel = m.group(1)
            dossier = m.group(2)
            document_and_file = m.group(3).split('-')[-1]
            document_barcode, file = document_and_file.split('_')
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'document_barcode': document_barcode,
                'file': file.split('.')[0],  # The file in the dossier
                'formatting': formatting,
                'source_file': source_file,
                'filename': relevant_url_part,  # The filename if this file needs to be stored on disc
            }

        elif source == 'wabo':  # = pre-wabo
            stadsdeel, dossier, olo_and_document = relevant_url_part.split('-', 2)
            olo, document_barcode = olo_and_document.split('_', 1)
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'olo': olo,
                'document_barcode': document_barcode,
                'formatting': formatting,
                'source_file': source_file,
                'filename': relevant_url_part,  # The filename if this file needs to be stored on disc
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception as e:
        log.error(f"Invalid iiif url: {iiif_url} ({e})")
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")


def img_is_public_copyright(metadata, document_barcode):
    """
    Return if document is public and has copyright.
    If it is not public the copyright is not used en returned as unknown
    """
    public = None
    copyright1 = None
    if metadata['access'] != settings.ACCESS_PUBLIC:
        public = False
    else:
        for meta_document in metadata['documenten']:
            if meta_document['barcode'] == document_barcode:
                if meta_document['access'] == settings.ACCESS_PUBLIC:
                    public = True
                    copyright1 = meta_document.get('copyright') == settings.COPYRIGHT_YES
                elif meta_document['access'] == settings.ACCESS_RESTRICTED:
                    public = False
                break
    if public is None:
        raise DocumentNotFoundInMetadataError()
    return public, copyright1


def create_mail_login_token(email_address, origin_url, key, expiry_hours=24):
    """
    Prepare a JSON web token to be used by the dataportaal. A link which includes this token is sent to the
    citizens email address which in turn leads them to the dataportaal. This enables citizens to view images
    by sending along this token along with every file request.
    """
    exp = int((datetime.utcnow() + timedelta(hours=expiry_hours)).timestamp())
    jwt_payload = {
        'sub': email_address,
        'exp': exp,
        'scopes': [settings.BOUWDOSSIER_PUBLIC_SCOPE],
        'origin_url': origin_url,  # Refers to the page from which the user originated. Can be used by the dataportaal to return the user to that same page
    }
    return jwt.encode(jwt_payload, key, algorithm=settings.JWT_ALGORITHM)


def check_auth_availability(request):
    if not request.META.get('HTTP_AUTHORIZATION') and not request.GET.get('auth') and not settings.DATAPUNT_AUTHZ['ALWAYS_OK']:
        return HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401)


def read_out_mail_jwt_token(request):
    jwt_token = {}
    if not request.META.get('HTTP_AUTHORIZATION'):
        if not request.GET.get('auth'):
            if settings.DATAPUNT_AUTHZ['ALWAYS_OK']:
                return jwt_token
            raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_NO_TOKEN, status=401))
        try:
            jwt_token = jwt.decode(request.GET.get('auth'), settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            # Check scopes
            for scope in jwt_token.get('scopes'):
                if scope not in (settings.BOUWDOSSIER_PUBLIC_SCOPE, settings.BOUWDOSSIER_READ_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE):
                    raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401))
        except ExpiredSignatureError:
            raise ImmediateHttpResponse(response=HttpResponse("Expired JWT token signature", status=401))
        except InvalidSignatureError:
            raise ImmediateHttpResponse(response=HttpResponse("Invalid JWT token signature", status=401))
        except DecodeError:
            raise ImmediateHttpResponse(response=HttpResponse("Invalid JWT token", status=401))
    return jwt_token


def get_max_scope(request, mail_jwt_token):
    # request.get_token_scopes gets the authz tokens
    # mail_jwt_token['scopes'] = jwt tokens which non-ambtenaren get in their email
    if settings.DATAPUNT_AUTHZ["ALWAYS_OK"]:
        scope = settings.BOUWDOSSIER_EXTENDED_SCOPE
    elif settings.BOUWDOSSIER_EXTENDED_SCOPE in request.get_token_scopes + mail_jwt_token.get('scopes', []):
        scope = settings.BOUWDOSSIER_EXTENDED_SCOPE
    elif settings.BOUWDOSSIER_READ_SCOPE in request.get_token_scopes + mail_jwt_token.get('scopes', []):
        scope = settings.BOUWDOSSIER_READ_SCOPE
    elif settings.BOUWDOSSIER_PUBLIC_SCOPE in mail_jwt_token.get('scopes', []):
        scope = settings.BOUWDOSSIER_PUBLIC_SCOPE
    else:
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401))

    return scope


def get_email_address(request, jwt_token):
    email_address = None
    if request.get_token_subject and '@' in request.get_token_subject:
        email_address = request.get_token_subject
    elif '@' in jwt_token.get('sub', ''):
        email_address = jwt_token['sub']

    if email_address is None:
        raise ImmediateHttpResponse(response=HttpResponse("No sub (email address) found in tokens", status=400))

    return email_address


def get_url_info(request, iiif_url):
    try:
        url_info = get_info_from_iiif_url(iiif_url, request.GET.get('source_file') == 'true')
    except InvalidIIIFUrlError:
        raise ImmediateHttpResponse(response=HttpResponse("Invalid formatted url", status=400))
    return url_info


def get_metadata(url_info, iiif_url):
    # Get the image metadata from the metadata server
    try:
        meta_response = get_meta_data(url_info)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER} "
            f"because of this error {e}"
        )
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_METADATA_SERVER, status=502))

    if meta_response.status_code == 404:
        raise ImmediateHttpResponse(response=HttpResponse("No metadata could be found for this dossier", status=404))
    elif meta_response.status_code != 200:
        log.info(
            f"Got response code {meta_response.status_code} while retrieving "
            f"the metadata for {iiif_url} from the stadsarchief metadata server."
        )
        raise ImmediateHttpResponse(response=HttpResponse(
            f"We had a problem retrieving the metadata. We got status code {meta_response.status_code}",
            status=400
        ))
    metadata = meta_response.json()

    return metadata


def check_file_access_in_metadata(metadata, url_info, scope):
    if scope not in (settings.BOUWDOSSIER_PUBLIC_SCOPE, settings.BOUWDOSSIER_EXTENDED_SCOPE, settings.BOUWDOSSIER_READ_SCOPE):
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_INVALID_SCOPE, status=401))
    # Check whether the image exists in the metadata
    try:
        is_public, has_copyright = img_is_public_copyright(metadata, url_info['document_barcode'])
        if is_public:
            if scope == settings.BOUWDOSSIER_PUBLIC_SCOPE and has_copyright:
                raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_COPYRIGHT, status=401))
        elif scope != settings.BOUWDOSSIER_EXTENDED_SCOPE:
            raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_RESTRICTED, status=401))
    except DocumentNotFoundInMetadataError:
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_NO_DOCUMENT_IN_METADATA, status=404))


def get_file(request_meta, url_info, iiif_url, metadata):
    # Get the file itself
    file_url, headers, cert = create_file_url_and_headers(request_meta, url_info, iiif_url, metadata)
    try:
        file_response = get_image_from_iiif_server(file_url, headers, cert)
    except RequestException as e:
        log.error(
            f"{RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE} "
            f"because of this error {e}"
        )
        raise ImmediateHttpResponse(response=HttpResponse(RESPONSE_CONTENT_ERROR_RESPONSE_FROM_CANTALOUPE, status=502))

    return file_response, file_url


def handle_file_response_errors(file_response, file_url):
    if file_response.status_code == 404:
        raise ImmediateHttpResponse(
            response=HttpResponse(f"No source file could be found for internal url {file_url}", status=404))
    elif file_response.status_code != 200:
        log.info(
            f"Got response code {file_response.status_code} while retrieving "
            f"the image {file_url} from the iiif-image-server."
        )
        raise ImmediateHttpResponse(response=HttpResponse(
            f"We had a problem retrieving the image. We got status "
            f"code {file_response.status_code} for internal url {file_url}",
            status=400
        ))


def check_for_post(request):
    if request.method != "POST":
        raise ImmediateHttpResponse(response=HttpResponseNotAllowed(['POST']))


def parse_payload(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        raise ImmediateHttpResponse(response=HttpResponse("JSON invalid", status=400))


def check_login_url_payload(payload):
    if not payload.get('email'):
        raise ImmediateHttpResponse(response=HttpResponse("No email found in json", status=400))
    if not payload.get('origin_url'):
        raise ImmediateHttpResponse(response=HttpResponse("No origin_url found in json", status=400))
    return payload['email'], payload['origin_url']


def check_email_validity(email_address):
    EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")  # Just basic sanity check for a @ and a dot
    if not EMAIL_REGEX.match(email_address):
        raise ImmediateHttpResponse(response=HttpResponse("Email is not valid", status=400))


def send_email(email_address, email_subject, email_body):
    if not settings.SENDGRID_KEY:
        log.error("No SENDGRID_KEY found. Not sending emails.")
    if '@' not in email_address:
        log.error("No valid email address. Not sending email.")

    sg = sendgrid.SendGridAPIClient(settings.SENDGRID_KEY)
    email = Mail(
        from_email='noreply@amsterdam.nl',
        to_emails=[email_address],
        subject=email_subject,
        html_content=email_body
    )
    sg.send(email)


def check_zip_payload(payload):
    if not payload.get('urls'):
        raise ImmediateHttpResponse(response=HttpResponse("No urls detected in json", status=400))


def strip_full_iiif_url(url):
    if '/iiif/' not in url:
        raise ImmediateHttpResponse(response=HttpResponse("Misformed paths", status=400))

    # Strip the domain from the url and return the only relevant part
    return url.split('/iiif/')[-1]


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
    zipjob_uuid = uuid4()
    tmp_folder_path = os.path.join('/tmp/', str(zipjob_uuid))
    os.mkdir(tmp_folder_path)
    return zipjob_uuid, tmp_folder_path


def save_file_to_folder(folder, filename, content):
    with open(os.path.join(folder, filename), 'w') as f:
        f.write(content)


def create_local_zip_file(zipjob_uuid, folder_path):
    zip_file_path = os.path.join('/tmp/', f'{zipjob_uuid}.zip')
    with ZipFile(zip_file_path, 'w') as zip_obj:
        for file in Path(folder_path).glob("*"):
            zip_obj.write(file, arcname=os.path.join(str(zipjob_uuid), file.name))
    return zip_file_path


def get_object_store_connection():
    return Connection(**settings.OBJECT_STORE)


def store_object_on_object_store(connection, local_zip_file_path, filename):
    with open(local_zip_file_path, 'r') as local:
        connection.put_object(
            settings.OBJECT_STORE_CONTAINER_NAME,
            filename,
            contents=local.read(),
            content_type='application/zip'
        )


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


def cleanup_local_files(zip_file_path, tmp_folder_path):
    # Cleanup the local zip file and folder with images
    os.remove(zip_file_path)
    shutil.rmtree(tmp_folder_path)


def remove_old_zips_from_object_store():
    conn = get_object_store_connection()

    # Get list of files from the object store
    headers, files = conn.get_container(settings.OBJECT_STORE_CONTAINER_NAME)
    log.info(f"Checking {headers['x-container-object-count']} files for removal")

    # Loop over files on object store and remove the old ones
    removed_counter = 0
    failed_counter = 0
    for file in files:
        file_age = datetime.now() - datetime.fromisoformat(file['last_modified'])
        if file_age.days > settings.TEMP_URL_EXPIRY_DAYS:
            try:
                conn.delete_object(settings.OBJECT_STORE_CONTAINER_NAME, file['name'])
                log.info(f"Removed {file['name']}")
                removed_counter += 1
            except ClientException as e:
                log.error(f"Failed to remove {file['name']} with error: {e}")
                failed_counter += 1

    log.info(f"\nSuccessfully removed {removed_counter} old files from the object store.\n")
    if failed_counter:
        log.info(f"\nFAILED removing {failed_counter} old files from the object store.\n")
