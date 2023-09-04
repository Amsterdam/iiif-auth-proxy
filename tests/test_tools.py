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

from iiif.authentication import create_mail_login_token, img_is_public_copyright
from iiif.image_server import create_file_url_and_headers, create_wabo_url
from iiif.parsing import InvalidIIIFUrlError, get_email_address, get_info_from_iiif_url
from iiif.tools import ImmediateHttpResponse
from iiif.zip_tools import TMP_BOUWDOSSIER_ZIP_FOLDER, create_local_zip_file
from tests.test_iiif import (
    PRE_WABO_IMG_URL,
    PRE_WABO_IMG_URL_NO_SCALING,
    PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE,
    PRE_WABO_INFO_JSON_URL,
    WABO_IMG_URL,
)
from tests.tools import filename_from_url

log = logging.getLogger(__name__)
timezone = pytz.timezone("UTC")


class TestTools:
    def setup_method(self):
        self.test_email_address = "toolstest@amsterdam.nl"

    def test_get_info_from_pre_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL, False)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_file"] == False

    def test_get_info_from_pre_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL, True)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_file"] == True

    def test_get_info_from_pre_wabo_url_with_no_scaling(self):
        url_info = get_info_from_iiif_url(PRE_WABO_IMG_URL_NO_SCALING, True)
        assert url_info["source"] == "edepot"
        assert url_info["stadsdeel"] == "ST"
        assert url_info["dossier"] == "00015"
        assert url_info["document_barcode"] == "ST00000126"
        assert url_info["file"] == "00001"
        assert url_info["scaling"] == "full"
        assert url_info["source_file"] == True

    def test_get_info_from_pre_wabo_url_wrong_formatted_url(self):
        with pytest.raises(InvalidIIIFUrlError):
            get_info_from_iiif_url("2/", False)

    def test_get_info_from_wabo_url_vanilla(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDZ"
        assert url_info["dossier"] == "38657"
        assert url_info["olo"] == "4900487"
        assert url_info["document_barcode"] == "628547"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_file"] == False

    def test_get_info_from_wabo_url_with_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, True)
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDZ"
        assert url_info["dossier"] == "38657"
        assert url_info["olo"] == "4900487"
        assert url_info["document_barcode"] == "628547"
        assert url_info["scaling"] == "1000,900"
        assert url_info["source_file"] == True

    def test_get_info_from_wabo_url_with_underscores_in_barcode(self):
        url_info = get_info_from_iiif_url(
            "2/wabo:SDO-10316333-3304_ECS0000004420_000_000/info.json", False
        )
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDO"
        assert url_info["dossier"] == "10316333"
        assert url_info["olo"] == "3304"
        assert url_info["document_barcode"] == "ECS0000004420_000_000"
        assert url_info["scaling"] == None
        assert url_info["source_file"] == False

    def test_get_info_from_wabo_url_with_underscores_and_hyphens_in_barcode(self):
        url_info = get_info_from_iiif_url(
            "2/wabo:SDO-10316333-3304_ECS0000004420-000_00-00/info.json", False
        )
        assert url_info["source"] == "wabo"
        assert url_info["stadsdeel"] == "SDO"
        assert url_info["dossier"] == "10316333"
        assert url_info["olo"] == "3304"
        assert url_info["document_barcode"] == "ECS0000004420-000_00-00"
        assert url_info["scaling"] == None
        assert url_info["source_file"] == False

    def test_get_info_from_wabo_url_wrong_formatted_url(self):
        with pytest.raises(InvalidIIIFUrlError):
            get_info_from_iiif_url("2/", False)

    def test_create_wabo_url(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, False)
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [{"filename": "SDZ/UIT/COH/628547.PDF"}],
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        assert wabo_url == "SDZ/UIT/COH/628547.PDF"

    def test_create_wabo_url_source_file(self):
        url_info = get_info_from_iiif_url(WABO_IMG_URL, True)
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [{"filename": "SDZ/UIT/COH/628547.PDF"}],
                }
            ]
        }

        wabo_url = create_wabo_url(metadata=metadata, url_info=url_info)
        assert wabo_url == "SDZ/UIT/COH/628547.PDF"

    def test_create_file_url_and_headers(self):
        metadata = {
            "documenten": [
                {
                    "barcode": "628547",
                    "bestanden": [{"filename": "SDZ/UIT/COH/628547.PDF"}],
                }
            ]
        }

        # pre-wabo with no headers
        url, headers, cert = create_file_url_and_headers(
            {}, {"source": "edepot", "source_file": False, "filename": filename_from_url(PRE_WABO_IMG_URL)}, PRE_WABO_IMG_URL, metadata
        )


        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{filename_from_url(PRE_WABO_IMG_URL)}"
        )
        assert headers == {'Authorization': settings.HCP_AUTHORIZATION}
        assert cert == ()

        # pre-wabo with source_file set to true
        url, headers, cert = create_file_url_and_headers(
            {},
            {
                "source": "edepot",
                "source_file": True,
                "filename": filename_from_url(PRE_WABO_IMG_URL),
            },
            PRE_WABO_IMG_URL,
            metadata,
        )
        assert url == f"{settings.EDEPOT_BASE_URL}{filename_from_url(PRE_WABO_IMG_URL)}"
        # assert headers["Authorization"] == settings.HCP_AUTHORIZATION
        assert cert == ()

        # pre-wabo with added reference
        url, headers, cert = create_file_url_and_headers(
            {},
            {"source": "edepot", "source_file": False, "filename": filename_from_url(PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE)},
            PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE,
            metadata,
        )
        # "2/edepot:SQ1452-SQ-01452%20(2)-SQ10079651_00001.jpg/full/1000,900/0/default.jpg"
        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{filename_from_url(PRE_WABO_IMG_URL_WITH_EXTRA_REFERENCE).replace('SQ1452/','')}"
        )

        # pre-wabo with json url
        url, headers, cert = create_file_url_and_headers(
            {},
            {"source": "edepot", "source_file": False, "filename": filename_from_url(PRE_WABO_INFO_JSON_URL)},
            PRE_WABO_INFO_JSON_URL,
            metadata,
        )

        assert (
            url
            == f"{settings.EDEPOT_BASE_URL}{filename_from_url(PRE_WABO_INFO_JSON_URL).replace('SQ11426/', '')}"
        )

        # wabo with adjusted url and X-Forwarded-ID
        url, headers, cert = create_file_url_and_headers(
            {},
            {
                "source": "wabo",
                "document_barcode": "628547",
                "formatting": "full/1000,1000/0/default.jpg",
                "source_file": False,
            },
            WABO_IMG_URL,
            metadata,
        )
        # WABO_IMG_URL = "2/wabo:SDZ-38657-4900487_628547/full/1000,900/0/default.jpg"
        assert (
            url
            == f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547.PDF"
        )
        # assert headers["X-Forwarded-ID"] == "wabo:SDZ-38657-4900487_628547"
        assert cert == '/tmp/sw444v1912.pem'

        # wabo with adjusted url and X-Forwarded-ID and both forwarded headers
        url, headers, cert = create_file_url_and_headers(
            {"HTTP_X_FORWARDED_PROTO": "proto", "HTTP_X_FORWARDED_HOST": "host"},
            {
                "source": "wabo",
                "document_barcode": "628547",
                "formatting": "full/1000,1000/0/default.jpg",
                "source_file": False,
            },
            WABO_IMG_URL,
            metadata,
        )
        assert (
            url
            == f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547.PDF"
        )
        assert cert == '/tmp/sw444v1912.pem'

        # wabo with source_file
        url, headers, cert = create_file_url_and_headers(
            {},
            {
                "source": "wabo",
                "document_barcode": "628547",
                "formatting": "full/1000,1000/0/default.jpg",
                "source_file": True,
            },
            WABO_IMG_URL,
            metadata,
        )
        assert url == f"{settings.WABO_BASE_URL}SDZ/UIT/COH/628547.PDF"
        assert cert == "/tmp/sw444v1912.pem"

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
        assert public == True
        assert has_copyright == False

        # Although this should not happen if on bouwdossier level access is restricted
        # and on document level it is public, the result shoulb be not public
        metadata = {
            "access": settings.ACCESS_RESTRICTED,
            "documenten": [{"barcode": "ST00000126", "access": settings.ACCESS_PUBLIC}],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public == False
        assert has_copyright == None

        metadata = {
            "access": settings.ACCESS_PUBLIC,
            "documenten": [
                {"barcode": "ST00000126", "access": settings.ACCESS_RESTRICTED}
            ],
        }
        public, has_copyright = img_is_public_copyright(metadata, "ST00000126")
        assert public == False
        assert has_copyright == None

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
        assert public == True
        assert has_copyright == True

    def test_create_local_zip_file(self):
        # First create some files
        uuid = str(uuid4())
        folder_path = f"{TMP_BOUWDOSSIER_ZIP_FOLDER}{uuid}/"
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
