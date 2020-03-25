import requests
from django.conf import settings


class InvalidIIIFUrlError(Exception):
    pass


class DocumentNotFoundInMetadataError(Exception):
    pass


def get_meta_data(stadsdeel, dossier, token):
    metadata_url = f"{settings.STADSARCHIEF_META_SERVER_BASE_URL}:" \
                   f"{settings.STADSARCHIEF_META_SERVER_PORT}/stadsarchief/bouwdossier/{stadsdeel}{dossier}/"
    return requests.get(metadata_url, headers={'Authorization': token})


def get_image_from_iiif_server(iiif_url, headers):
    iiif_image_url = f"{settings.IIIF_BASE_URL}:{settings.IIIF_PORT}/iiif/{iiif_url}"
    return requests.get(iiif_image_url, headers=headers)


def get_info_from_iiif_url(iiif_url):
    # iiif_url = \
    # "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST-00015-ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST=stadsdeel  00015=dossier  ST00000126=document  00001=file/bestand

    try:
        relevant_url_part = iiif_url.split('edepot:')[1].split('/')[0]
        stadsdeel, dossier, document_and_file = relevant_url_part.split('-')
        document, file = document_and_file.split('_')
        return stadsdeel, dossier, document, file.split('.')[0]
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
