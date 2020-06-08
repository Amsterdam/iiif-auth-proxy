import requests
from django.conf import settings


class InvalidIIIFUrlError(Exception):
    pass


class DocumentNotFoundInMetadataError(Exception):
    pass


def get_meta_data(url_info, token):
    # Test with:
    # curl -i -H "Accept: application/json" http://iiif-metadata-server.service.consul:8183/iiif-metadata/bouwdossier/SA85385/
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/iiif-metadata/bouwdossier/{url_info['stadsdeel']}{url_info['dossier']}/"
    return requests.get(metadata_url, headers={'Authorization': token})


def create_wabo_url(url_info, metadata):
    for document in metadata['documenten']:
        if document['barcode'] == url_info['document_barcode']:
            return f"2/{url_info['source']}:{document['bestanden'][0]['filename']}/{url_info['formatting']}"

    # TODO: raise something in the unlikely event that nothing is found


def get_image_from_iiif_server(iiif_url, headers):
    iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{iiif_url}"
    return requests.get(iiif_image_url, headers=headers)


def get_info_from_iiif_url(iiif_url):
    ## PRE-WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST=stadsdeel  00015=dossier  ST00000126=document_barcode  00001=file/bestand

    ## WABO
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/wabo:SDZ-38657-4900487_628547"
    # SDZ=stadsdeel  38657=dossier  4900487=olo_liaan_nummer  628547=document_barcode

    try:
        source = iiif_url.split(':')[0].split('/')[1]
        relevant_url_part = iiif_url.split(':')[1].split('/')[0]
        formatting = iiif_url.split(':')[1].split('/', 1)[1] if '/' in iiif_url.split(':')[1] else ''

        if source == 'edepot':  # == pre-wabo
            stadsdeel, dossier, document_and_file = relevant_url_part.split('-')
            document_barcode, file = document_and_file.split('_')
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'document_barcode': document_barcode,
                'file': file.split('.')[0],
                'formatting': formatting
            }

        elif source == 'wabo':  # = pre-wabo
            stadsdeel, dossier, olo_and_document = relevant_url_part.split('-')
            olo, document_barcode = olo_and_document.split('_')
            return {
                'source': source,
                'stadsdeel': stadsdeel,
                'dossier': dossier,
                'olo': olo,
                'document_barcode': document_barcode,
                'formatting': formatting
            }

        raise InvalidIIIFUrlError(f"Invalid iiif url (no valid source): {iiif_url}")

    except Exception:
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
