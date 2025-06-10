import os

from django.conf import settings

EDEPOT_PREFIX = "2/edepot:"
WABO_PREFIX = "2/wabo:"

PRE_WABO_IMG_URL_BASE = EDEPOT_PREFIX + "ST_00015~ST00000126_1/"
PRE_WABO_INFO_JSON_URL = PRE_WABO_IMG_URL_BASE + "info.json"

PRE_WABO_IMG_URL_WITH_SCALING = PRE_WABO_IMG_URL_BASE + "full/50,50/0/default.jpg"
PRE_WABO_IMG_URL_WITH_EMPTY_SCALING = PRE_WABO_IMG_URL_BASE + "full//0/default.jpg"

PRE_WABO_IMG_URL_WITH_REGION = PRE_WABO_IMG_URL_BASE + "24,24,48,48/full/0/default.jpg"
PRE_WABO_IMG_URL_WITH_REGION_NON_OVERLAPPING = (
    PRE_WABO_IMG_URL_BASE + "10000,10000,48,48/full/0/default.jpg"
)

PRE_WABO_IMG_URL_SOURCE_FILE = (
    PRE_WABO_IMG_URL_BASE+"?source_file=true&"
)
PRE_WABO_IMG_URL_NO_SCALING = (
    PRE_WABO_IMG_URL_BASE+"full/full/0/default.jpg"
)

PRE_WABO_IMG_URL_DOUBLE_DOSSIER = (
    EDEPOT_PREFIX + "SQ_01452X~SQ10079651_1/full/full/0/default.jpg"
)

PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE = (
    EDEPOT_PREFIX
    + "SQ_01452~SQ-01452%20(2)-SQ10079651_1/full/full/0/default.jpg"
)
PRE_WABO_IMG_URL_WITH_CHARS_IN_DOSSIER = (
    EDEPOT_PREFIX
    + "SQ_28276-SQ-file9EyinW~SQ10263352_3/full/full/0/default.jpg"
)

PRE_WABO_IMG_URL_WITH_LOWERCASE_IN_DOSSIER = (
    EDEPOT_PREFIX + "SQ_26614abc~sq10241283_1/full/full/0/default.jpg"
)

WABO_IMG_URL = WABO_PREFIX + "SDZ_TA-38657~628547_1/full/1000,900/0/default.jpg"
WABO_IMG_URL2 = (
    WABO_PREFIX + "SDZ_TA-38657~628547_2/full/1000,900/0/default.jpg"
)

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

with open(
    os.path.join(CURRENT_DIRECTORY, "test-images/test-image-96x85.jpg"), "rb"
) as file:
    IMAGE_BINARY_DATA = file.read()
with open(
    os.path.join(CURRENT_DIRECTORY, "test-images/test-image-50x44.jpg"), "rb"
) as file:
    IMAGE_BINARY_DATA_50x44 = file.read()
with open(
    os.path.join(CURRENT_DIRECTORY, "test-images/test-image-cropped-24x24x72x72.jpg"),
    "rb",
) as file:
    IMAGE_BINARY_DATA_24x24x72x72 = file.read()

DEFAULT_META_BESTAND = {
                            "filename": "ST00000126.jpg",
                            "file_pad": 'SDC/BWT/ST00000126.jpg',
                            "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_1~ST00000126_1"
                        }

PRE_WABO_METADATA_CONTENT = {
    "access": settings.ACCESS_PUBLIC,
    "documenten": [
        {
            "barcode": "ST00000126",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_YES,
            "bestanden": [
                    {
                        "filename": "test.doc",
                        "file_pad": "ST/15/test.doc",
                        "url": "https://bouwdossiers.amsterdam.nl/iiif/2/edepot:ST_00015~ST00000126_1"
                    }
                ],
        },
        {
            "barcode": "SQ10079651",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_YES,
            "bestanden": [
                    {
                        "filename": "SQ10079651.jpg",
                        "file_pad": "SQ/01452 (2)/SQ10079651.jpg",
                        "url": "https://bouwdossiers.amsterdam.nl/iiif/2/edepot:SQ_01452~SQ10079651_1"
                    }
                ],            
        },
        {
            "barcode": "SQ10092307", 
            "access": settings.ACCESS_PUBLIC,
            "bestanden": [
                    {
                        "filename": "test.jpg",
                        "file_pad": "SDC/00003/KEY2/test.jpg",
                        "url": "https://bouwdossiers.amsterdam.nl/iiif/2/wabo:SDC_3~NAA%2002111056_1"
                    }
                ],
        },
    ],
}
