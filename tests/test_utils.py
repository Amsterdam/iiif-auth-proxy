import logging
import os
import shutil
from collections import namedtuple
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import jwt
import pytest
import pytz
from django.conf import settings

from auth_mail.authentication import create_mail_login_token, img_is_public_copyright
from iiif.image_server import create_file_url_and_headers, create_wabo_url
from iiif.parsing import InvalidIIIFUrlError, get_email_address, get_info_from_iiif_url
from main.utils import ImmediateHttpResponse
from tests.test_settings import (
    PRE_WABO_IMG_URL_NO_SCALING,
    PRE_WABO_IMG_URL_DOUBLE_DOSSIER,
    PRE_WABO_IMG_URL_WITH_CHARS_IN_DOSSIER,
    PRE_WABO_IMG_URL_WITH_EXTRA_DOSSIER_DIGIT,
    PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE,
    PRE_WABO_IMG_URL_WITH_LOWERCASE_IN_DOSSIER,
    PRE_WABO_IMG_URL_WITH_REGION,
    PRE_WABO_IMG_URL_WITH_SCALING,
    PRE_WABO_INFO_JSON_URL,
    WABO_IMG_URL,
    WABO_IMG_URL2,
)
from tests.tools import filename_from_url, source_filename_from_url
from zip_consumer.zip_tools import TMP_BOUWDOSSIER_ZIP_FOLDER, create_local_zip_file

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


class TestUtils:
    def setup_method(self):
        self.test_email_address = "toolstest@amsterdam.nl"

    def test_get_info_json_from_pre_wabo_url(self):
        """2/edepot:ST_00015~ST00000126_00001.jpg/"""
        url_info = get_info_from_iiif_url(PRE_WABO_INFO_JSON_URL, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["region"] is None
        assert url_info["scaling"] is None
        assert url_info["source_filename"] == "ST/00015/ST00000126_00001.jpg"
        assert url_info["filename"] == "ST_00015~ST00000126_00001.jpg"
        assert url_info["formatting"] is None
        assert url_info["info_json"] is True

    def test_get_info_json_from_pre_wabo_url_with_extra_digit(self):
        """2/edepot:SA_100732~SA00509506_00003.jpg/"""
        url_info = get_info_from_iiif_url(
            PRE_WABO_IMG_URL_WITH_EXTRA_DOSSIER_DIGIT, False
        )
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "SA"
        assert url_info["dossier"] == "100732"
        assert url_info["document_barcode"] == "SA00509506"
        assert url_info["file"] == "00003"
        assert url_info["region"] is None
        assert url_info["scaling"] is None
        assert url_info["source_filename"] == "SA/100732/SA00509506_00003.jpg"
        assert url_info["filename"] == "SA_100732~SA00509506_00003.jpg"
        assert url_info["formatting"] is None
        assert url_info["info_json"] is True

    def test_get_info_json_from_pre_wabo_url_double_dossier(self):
        """2/edepot:SQ_01452X~SQ-01452-SQ10079651_00001.jpg"""
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_DOUBLE_DOSSIER, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "SQ"
        assert url_info["dossier"] == "01452X"
        assert url_info["document_barcode"] == "SQ10079651"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "full"
        assert url_info["source_filename"] == "SQ/01452/SQ10079651_00001.jpg"
        assert url_info["filename"] == "SQ_01452X~SQ-01452-SQ10079651_00001.jpg"
        assert url_info["formatting"] == "full/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_json_from_pre_wabo_url_with_extra_reference(self):
        """2/edepot:SQ_01452~SQ-01452%20(2)-SQ10079651_00001.jpg"""
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "SQ"
        assert url_info["dossier"] == "01452"
        assert url_info["document_barcode"] == "SQ10079651"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "full"
        assert url_info["source_filename"] == "SQ/01452%20(2)/SQ10079651_00001.jpg"
        assert url_info["filename"] == "SQ_01452~SQ-01452%20(2)-SQ10079651_00001.jpg"
        assert url_info["formatting"] == "full/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_json_from_pre_wabo_url_with_characters_in_dossier(self):
        """SQ_28276-SQ-file9EyinW~SQ10263352_00003.jpg/full/full/0/default.jpg"""
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_WITH_CHARS_IN_DOSSIER, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "SQ"
        assert url_info["dossier"] == "28276-SQ-file9EyinW"
        assert url_info["document_barcode"] == "SQ10263352"
        assert url_info["file"] == "00003"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "full"
        assert (
            url_info["source_filename"] == "SQ/28276-SQ-file9EyinW/SQ10263352_00003.jpg"
        )
        assert url_info["filename"] == "SQ_28276-SQ-file9EyinW~SQ10263352_00003.jpg"
        assert url_info["formatting"] == "full/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_json_from_pre_wabo_url_with_lowercase_in_dossier(self):
        """SQ_26614~sq10241283_00001.jpg/full/full/0/default.jpg"""
        url_info = get_info_from_iiif_url(
            PRE_WABO_IMG_URL_WITH_LOWERCASE_IN_DOSSIER, False
        )
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "SQ"
        assert url_info["dossier"] == "26614"
        assert url_info["document_barcode"] == "SQ10241283"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "full"
        assert url_info["source_filename"] == "SQ/26614/sq10241283_00001.jpg"
        assert url_info["filename"] == "SQ_26614~sq10241283_00001.jpg"
        assert url_info["formatting"] == "full/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_pre_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_WITH_SCALING, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "50,50"
        assert url_info["source_filename"] == "ST/00015/ST00000126_00001.jpg"
        assert url_info["filename"] == "ST_00015~ST00000126_00001.jpg"
        assert url_info["formatting"] == "full/50,50/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_pre_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_WITH_SCALING, True)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "50,50"
        assert url_info["source_filename"] == "ST/00015/ST00000126_00001.jpg"
        assert url_info["filename"] == "ST_00015~ST00000126_00001.jpg"
        assert url_info["formatting"] == "full/50,50/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_pre_wabo_url_with_no_scaling(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_NO_SCALING, True)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "full"
        assert url_info["source_filename"] == "ST/00015/ST00000126_00001.jpg"
        assert url_info["filename"] == "ST_00015~ST00000126_00001.jpg"
        assert url_info["formatting"] == "full/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_pre_wabo_url_with_cropping(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_WITH_REGION, True)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["region"] == "24,24,48,48"
        assert url_info["scaling"] == "full"
        assert url_info["source_filename"] == "ST/00015/ST00000126_00001.jpg"
        assert url_info["filename"] == "ST_00015~ST00000126_00001.jpg"
        assert url_info["formatting"] == "24,24,48,48/full/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_pre_wabo_url_wrong_formatted_url(self):
        with pytest.raises(InvalidIIIFUrlError):
            get_info_from_iiif_url("2/", False)

    def test_get_info_from_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDZ"
        assert url_info["dossier"] == "TA-38657"
        assert url_info["olo"] == "4900487"
        assert url_info["document_barcode"] == "628547"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_filename"] == "SDZ/TA-38657/4900487_628547_1"
        assert url_info["filename"] == "SDZ_TA-38657~4900487_628547_1"
        assert url_info["formatting"] == "full/1000,900/0/default.jpg"
        assert url_info["info_json"] is False

    def test_get_info_from_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, True)
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDZ"
        assert url_info["dossier"] == "TA-38657"
        assert url_info["olo"] == "4900487"
        assert url_info["document_barcode"] == "628547"
        assert url_info["region"] == "full"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_filename"] == "SDZ/TA-38657/4900487_628547_1"
        assert url_info["filename"] == "SDZ_TA-38657~4900487_628547_1"
        assert url_info["formatting"] == "full/1000,900/0/default.jpg"
        assert url_info["info_json"] is False

    @pytest.mark.xfail(
        reason="WABO dossiers barcodes don't have underscores see metadata-server batch.py"
    )
    def test_get_info_from_wabo_url_with_underscores_in_barcode(self):
        url_info = get_info_from_iiif_url(
            "2/wabo:SDO_T-10316333~3304_ECS0000004420_000_000/info.json", False
        )
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDO"
        assert url_info["dossier"] == "T-10316333"
        assert url_info["olo"] == "3304"
        assert url_info["document_barcode"] == "ECS0000004420_000_000"
        assert url_info["region"] is None
        assert url_info["scaling"] is None
        assert (
            url_info["source_filename"] == "SDO/T-10316333/3304_ECS0000004420_000_000"
        )
        assert url_info["filename"] == "SDO_T-10316333~3304_ECS0000004420_000_000"
        assert url_info["formatting"] is None
        assert url_info["info_json"] is True

    def test_get_info_from_wabo_url_with_hyphens_in_barcode(self):
        url_info = get_info_from_iiif_url(
            "2/wabo:SDO_10316333~3304_ECS0000004420-000-00-00_2/info.json", False
        )
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDO"
        assert url_info["dossier"] == "10316333"
        assert url_info["olo"] == "3304"
        assert url_info["document_barcode"] == "ECS0000004420-000-00-00"
        assert url_info["filenr"] == "2"
        assert url_info["region"] is None
        assert url_info["scaling"] is None
        assert (
            url_info["source_filename"] == "SDO/10316333/3304_ECS0000004420-000-00-00_2"
        )
        assert url_info["filename"] == "SDO_10316333~3304_ECS0000004420-000-00-00_2"
        assert url_info["formatting"] is None
        assert url_info["info_json"] is True

    def test_get_info_from_wabo_url_wrong_formatted_url(self):
        with pytest.raises(InvalidIIIFUrlError):
            get_info_from_iiif_url("2/", False)

    def test_create_wabo_url(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [
                        {"filename": "SDZ/UIT/COH/628547_00001.PDF"},
                        {"filename": "SDZ/UIT/COH/628547_11119.jpg"},
                    ],
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        assert wabo_url == "SDZ/UIT/COH/628547_00001.PDF"

    def test_create_wabo_url_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL2, True)
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [
                        {"filename": "SDZ/UIT/COH/628547_00001.PDF"},
                        {"filename": "SDZ/UIT/COH/628547_11119.jpg"},
                    ],
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        assert wabo_url == "SDZ/UIT/COH/628547_11119.jpg"

    def test_create_file_url_and_headers(self):
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [
                        {"filename": "SDZ/UIT/COH/628547_00001.PDF"},
                        {"filename": "SDZ/UIT/COH/628547_11119.jpg"},
                    ],
                },
            ]
        }

        # pre-wabo with no headers
        url, headers = create_file_url_and_headers(
            {
                "source": "edepot",
                "source_filename": source_filename_from_url(
                    PRE_WABO_IMG_URL_WITH_SCALING
                ),
                "filename": filename_from_url(PRE_WABO_IMG_URL_WITH_SCALING),
            },
            metadata,
        )

        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{source_filename_from_url(PRE_WABO_IMG_URL_WITH_SCALING)}"
        )
        assert headers == {"Authorization": settings.EDEPOT_AUTHORIZATION}

        # pre-wabo with source_file set to true
        url, headers = create_file_url_and_headers(
            {
                "source": "edepot",
                "source_filename": source_filename_from_url(
                    PRE_WABO_IMG_URL_WITH_SCALING
                ),
                "filename": filename_from_url(PRE_WABO_IMG_URL_WITH_SCALING),
            },
            metadata,
        )
        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{source_filename_from_url(PRE_WABO_IMG_URL_WITH_SCALING)}"
        )
        assert headers["Authorization"] == settings.EDEPOT_AUTHORIZATION

        # pre-wabo with added reference
        url, headers = create_file_url_and_headers(
            {
                "source": "edepot",
                "source_filename": source_filename_from_url(
                    PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE
                ),
                "filename": filename_from_url(PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE),
            },
            metadata,
        )
        # "2/edepot:SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/1000,900/0/default.jpg"
        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{source_filename_from_url(PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE).replace('SQ1452/', '')}"
        )

        # pre-wabo with json url
        url, headers = create_file_url_and_headers(
            {
                "source": "edepot",
                "source_filename": source_filename_from_url(PRE_WABO_INFO_JSON_URL),
                "filename": filename_from_url(PRE_WABO_INFO_JSON_URL),
            },
            metadata,
        )

        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{source_filename_from_url(PRE_WABO_INFO_JSON_URL).replace('SQ11426/', '')}"
        )

        # wabo source get file 2 from metadata
        url, headers = create_file_url_and_headers(
            {
                "source": "wabo",
                "document_barcode": "628547",
                "filenr": "2",
                "formatting": "full/1000,1000/0/default.jpg",
            },
            metadata,
        )
        # WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547_2/full/1000,900/0/default.jpg"
        assert url == f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547_11119.jpg"

        # wabo source get file 1 from metadata
        url, headers = create_file_url_and_headers(
            {
                "source": "wabo",
                "document_barcode": "628547",
                "filenr": "1",
                "formatting": "full/1000,1000/0/default.jpg",
            },
            metadata,
        )
        # WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547_2/full/1000,900/0/default.jpg"
        assert url == f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547_00001.PDF"

    def test_get_authentication_jwt(self):
        token = create_mail_login_token("jwttest@amsterdam.nl", settings.SECRET_KEY)
        decoded = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert len(decoded.keys()) == 3
        assert "exp" in decoded.keys()
        assert "scopes" in decoded.keys()
        assert "sub" in decoded.keys()
        assert decoded["sub"] == "jwttest@amsterdam.nl"
        assert len(decoded["scopes"]) == 1
        assert decoded["scopes"][0] == settings.BOUWDOSSIER_PUBLIC_SCOPE

    def test_img_is_public_copyright(self):
        metadata = {
            "access": settings.ACCESS_PUBLIC,
            "documenten": [{"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public is True
        assert has_copyright is False

        # Although this should not happen if on bouwdossier level access is restricted
        # and on document level it is public, the result shoulb be not public
        metadata = {
            "access": settings.ACCESS_RESTRICTED,
            "documenten": [{"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public is False
        assert has_copyright is None

        metadata = {
            "access": settings.ACCESS_PUBLIC,
            "documenten": [
                {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
            ],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public is False
        assert has_copyright is None

        metadata = {
            "access": settings.ACCESS_PUBLIC,
            "documenten": [
                {
                    "barcode": "ST00000126",
                    "access": settings.ACCESS_PUBLIC,
                    "copyright": settings.COPYRIGHT_YES,
                }
            ],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public is True
        assert has_copyright is True

    def test_create_local_zip_file(self):
        # First create some files
        uuid = str(uuid4())
        folder_path = os.path.join(TMP_BOUWDOSSIER_ZIP_FOLDER, uuid)
        os.makedirs(folder_path)
        filenames = [f"content{i}.txt" for i in range(5)]
        for filename in filenames:
            with open(f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{uuid}/{filename}", "w") as f:
                f.write("content")

        # Create the zip file
        create_local_zip_file(uuid, folder_path)

        # Check whether the newly created zip file exists
        assert Path(f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{uuid}.zip").is_file()

        # Unzip the file
        unzip_uuid = uuid4()
        unzip_folder = f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{unzip_uuid}/"
        os.mkdir(unzip_folder)
        with ZipFile(f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{uuid}.zip", "r") as zip_ref:
            zip_ref.extractall(unzip_folder)

        os.path.isdir(os.path.join(unzip_folder, uuid))
        extracted_files = sorted(
            [file.name for file in Path(os.path.join(unzip_folder, uuid)).glob("*")]
        )
        assert extracted_files == filenames

        # Cleanup so that other tests are not influenced
        shutil.rmtree(folder_path)
        os.remove(f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{uuid}.zip")
        shutil.rmtree(unzip_folder)

    def test_get_email_address(self):
        Request = namedtuple("Request", "get_token_subject, get_token_claims")

        # test getting the email address from the authz token
        request = Request(
            get_token_subject=self.test_email_address, get_token_claims={}
        )
        assert get_email_address(request, {"sub": "a@a.a"}) == self.test_email_address

        # test getting the email address from the email login link jwt token
        request = Request(get_token_subject=None, get_token_claims={})
        assert (
            get_email_address(request, {"sub": self.test_email_address})
            == self.test_email_address
        )

        # test getting the email address from the keycloak token
        request = Request(
            get_token_subject=None, get_token_claims={"email": self.test_email_address}
        )
        assert (
            get_email_address(request, {"sub": "other str"}) == self.test_email_address
        )

        # test getting no email address from any token
        request = Request(get_token_subject=None, get_token_claims={})
        with pytest.raises(ImmediateHttpResponse):
            get_email_address(request, {"sub": "other str"})
