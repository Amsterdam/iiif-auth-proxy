import re
import requests
from django.conf import settings


class InvalidIIIFUrlError(Exception):
    pass


class DocumentNotFoundInMetadataError(Exception):
    pass


def get_meta_data(url_info, token):
    # Test with:
    # curl -i -H "Accept: application/json" http://iiif-metadata-server-api.service.consul:8183/iiif-metadata/bouwdossier/SA85385/
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}{url_info['dossier']}/"
    return requests.get(metadata_url, headers={'Authorization': token})


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
    # ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand

    ## WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547/full/full/0/default.jpg""
    # SDZ=stadsdeel  38657=dossier  4900487=olo_liaan_nummer  628547=document_barcode

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
                'file': file.split('.')[0],
                'formatting': formatting,
                'source_file': source_file,
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
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception as e:
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")


def img_is_public(metadata, document_barcode):
    if metadata['access'] != settings.ACCESS_PUBLIC:
        return False

    for meta_document in metadata['documenten']:
        if meta_document['barcode'] == document_barcode:
            if meta_document['access'] == settings.ACCESS_PUBLIC:
                return True
            elif meta_document['access'] == settings.ACCESS_RESTRICTED:
                return False
            break
    raise DocumentNotFoundInMetadataError()
