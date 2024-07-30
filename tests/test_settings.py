from django.conf import settings

EDEPOT_PREFIX = "2/edepot:"
WABO_PREFIX = "2/wabo:"

PRE_WABO_IMG_URL_BASE = EDEPOT_PREFIX + "ST-00015-ST00000126_00001.jpg/"
PRE_WABO_INFO_JSON_URL = PRE_WABO_IMG_URL_BASE + "info.json"

PRE_WABO_IMG_URL_WITH_SCALING = PRE_WABO_IMG_URL_BASE + "full/50,50/0/default.jpg"
PRE_WABO_IMG_URL_WITH_EMPTY_SCALING = PRE_WABO_IMG_URL_BASE + "full//0/default.jpg"

PRE_WABO_IMG_URL_WITH_REGION = PRE_WABO_IMG_URL_BASE + "24,24,48,48/full/0/default.jpg"
PRE_WABO_IMG_URL_WITH_REGION_NON_OVERLAPPING = (
    PRE_WABO_IMG_URL_BASE + "10000,10000,48,48/full/0/default.jpg"
)

PRE_WABO_IMG_URL_SOURCE_FILE = (
    EDEPOT_PREFIX + "ST-00015-ST00000126_00001.jpg/?source_file=true&"
)
PRE_WABO_IMG_URL_NO_SCALING = (
    EDEPOT_PREFIX + "ST-00015-ST00000126_00001.jpg/full/full/0/default.jpg"
)

PRE_WABO_IMG_URL_WITH_EXTRA_DOSSIER_DIGIT = (
    EDEPOT_PREFIX + "SA-100732-SA00509506_00003.jpg/info.json"
)
PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE = (
    EDEPOT_PREFIX + "SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/full/0/default.jpg"
)
PRE_WABO_IMG_URL_WITH_CHARS_IN_DOSSIER = (
    EDEPOT_PREFIX + "SQ28276-SQ-file9EyinW-SQ10263352_00003.jpg/full/full/0/default.jpg"
)

WABO_IMG_URL = WABO_PREFIX + "SDZ-38657-4900487_628547/full/1000,900/0/default.jpg"

with open("test-images/test-image-96x85.jpg", "rb") as file:
    IMAGE_BINARY_DATA = file.read()
with open("test-images/test-image-50x44.jpg", "rb") as file:
    IMAGE_BINARY_DATA_50x44 = file.read()
with open("test-images/test-image-cropped-24x24x72x72.jpg", "rb") as file:
    IMAGE_BINARY_DATA_24x24x72x72 = file.read()

PRE_WABO_METADATA_CONTENT = {
    "access": settings.ACCESS_PUBLIC,
    "documenten": [
        {
            "barcode": "ST00000126",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_YES,
        },
        {
            "barcode": "SQ10079651",
            "access": settings.ACCESS_PUBLIC,
            "copyright": settings.COPYRIGHT_NO,
        },
        {"barcode": "SQ10092307", "access": settings.ACCESS_PUBLIC},
    ],
}
