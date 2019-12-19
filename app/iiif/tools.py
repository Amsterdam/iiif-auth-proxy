class InvalidIIIFUrlError(Exception):
    pass


def get_info_from_iiif_url(iiif_url):
    # iiif_url = "https://acc.images.data.amsterdam.nl/iiif/2/edepot:ST$00015$ST00000126_00001.jpg/full/1000,1000/0/default.jpg"
    # ST=stadsdeel  00015=dossier  ST00000126=subdossier  00001=image
    try:
        relevant_url_part = iiif_url.split('edepot:')[1].split('/')[0]
        stadsdeel, dossier, subdossier_and_image = relevant_url_part.split('$')
        subdossier, image = subdossier_and_image.split('_')
        return stadsdeel, dossier, subdossier, image.split('.')[0]
    except Exception:
        raise InvalidIIIFUrlError(f"Invalid iiif url: {iiif_url}")
