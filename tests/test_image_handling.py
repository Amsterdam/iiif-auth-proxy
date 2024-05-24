import pytest

from iiif.image_handling import (
    NON_OVERLAPPING_REGION_PARAMETER,
    crop_image,
    parse_region_string,
    parse_scaling_string,
    scale_image,
)
from main.utils import ImmediateHttpResponse


class TestImageFormatting:
    def setup_method(self):
        with open("test-images/test-image-96x85.jpg", "rb") as f:
            self.img_96x85 = f.read()
        with open("test-images/test-image-50x44.jpg", "rb") as f:
            self.img_50x44 = f.read()
        with open("test-images/test-image-49x44.jpg", "rb") as f:
            self.img_49x44 = f.read()
        with open("test-images/test-image-cropped-0x0x50x44.jpg", "rb") as f:
            self.img_0x0x50x44 = f.read()
        with open("test-images/test-image-cropped-0x41x96x44.jpg", "rb") as f:
            self.img_0x41x96x44 = f.read()
        with open("test-images/test-image-cropped-24x24x72x72.jpg", "rb") as f:
            self.img_24x24x72x72 = f.read()
        with open("test-images/test-image-cropped-48x0x48x85.jpg", "rb") as f:
            self.img_48x0x48x85 = f.read()
        with open("test-images/test-image-cropped-85x85.jpg", "rb") as f:
            self.img_85x85 = f.read()

    @pytest.mark.parametrize("param", [None, "", ",", "w,h"])
    def test_parse_invalid_scaling_string_raises(self, param):
        with pytest.raises(ImmediateHttpResponse):
            parse_scaling_string(param)

    def test_parse_scaling_string(self):
        assert parse_scaling_string("100,") == (100, None)
        assert parse_scaling_string(",100") == (None, 100)
        assert parse_scaling_string("100,100") == (100, 100)

    def test_scale_image(self):
        assert (
            scale_image(False, "image/jpeg", "full", self.img_96x85) == self.img_96x85
        )
        assert (
            scale_image(False, "image/jpeg", "100,100", self.img_96x85)
            == self.img_96x85
        )
        assert (
            scale_image(False, "image/jpeg", "100,", self.img_96x85) == self.img_96x85
        )
        assert (
            scale_image(False, "image/jpeg", ",100", self.img_96x85) == self.img_96x85
        )
        assert (
            scale_image(False, "image/jpeg", "50,50", self.img_96x85) == self.img_50x44
        )
        assert scale_image(False, "image/jpeg", "50,", self.img_96x85) == self.img_50x44
        assert (
            scale_image(False, "image/jpeg", "60,44", self.img_96x85) == self.img_49x44
        )
        assert scale_image(False, "image/jpeg", ",44", self.img_96x85) == self.img_49x44

    @pytest.mark.parametrize("param", [None, "", ",,,", "x,y,w,h", "50,50,,"])
    def test_parse_invalid_region_string_raises(self, param):
        with pytest.raises(ImmediateHttpResponse):
            parse_region_string(param)

    def test_parse_region_string(self):
        assert parse_region_string("-50,-56,100,100") == (-50, -56, 100, 100)
        assert parse_region_string("0,0,50,44") == (0, 0, 50, 44)

    def test_crop_image(self):
        assert crop_image(False, "image/jpeg", "full", self.img_96x85) == self.img_96x85
        assert (
            crop_image(False, "image/jpeg", "square", self.img_96x85) == self.img_85x85
        )
        assert (
            crop_image(False, "image/jpeg", "0,0,100,100", self.img_96x85)
            == self.img_96x85
        )
        assert (
            crop_image(False, "image/jpeg", "0,0,50,44", self.img_96x85)
            == self.img_0x0x50x44
        )
        assert (
            crop_image(False, "image/jpeg", "24,24,48,48", self.img_96x85)
            == self.img_24x24x72x72
        )
        assert (
            crop_image(False, "image/jpeg", "0,41,96,85", self.img_96x85)
            == self.img_0x41x96x44
        )
        assert (
            crop_image(False, "image/jpeg", "48,0,96,85", self.img_96x85)
            == self.img_48x0x48x85
        )
        assert (
            crop_image(False, "image/jpeg", "-50,-56,100,100", self.img_96x85)
            == self.img_0x0x50x44
        )

    def test_crop_image_no_size(self):
        with pytest.raises(ImmediateHttpResponse):
            crop_image(False, "image/jpeg", "0,0,0,0", self.img_96x85)

    def test_crop_outside_image(self):
        with pytest.raises(ImmediateHttpResponse):
            crop_image(False, "image/jpeg", "100,100,50,50", self.img_96x85)
