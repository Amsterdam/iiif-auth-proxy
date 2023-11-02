import pytest

from iiif.image_handling import (
    NON_OVERLAPPING_REGION_PARAMETER,
    crop_image,
    parse_region_string,
    parse_scaling_string,
    scale_image,
)


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

    def test_parse_scaling_string(self):
        assert parse_scaling_string("100,") == (100, None)
        assert parse_scaling_string(",100") == (None, 100)
        assert parse_scaling_string("100,100") == (100, 100)

    def test_scale_image(self):
        assert scale_image(self.img_96x85, False, "full", "image/jpeg") == self.img_96x85
        assert scale_image(self.img_96x85, False, "100,100", "image/jpeg") == self.img_96x85
        assert scale_image(self.img_96x85, False, "100,", "image/jpeg") == self.img_96x85
        assert scale_image(self.img_96x85, False, ",100", "image/jpeg") == self.img_96x85
        assert scale_image(self.img_96x85, True, "20,20", "image/jpeg") == self.img_96x85
        assert scale_image(self.img_96x85, False, "50,50", "image/jpeg") == self.img_50x44
        assert scale_image(self.img_96x85, False, "50,", "image/jpeg") == self.img_50x44
        assert scale_image(self.img_96x85, False, "60,44", "image/jpeg") == self.img_49x44
        assert scale_image(self.img_96x85, False, ",44", "image/jpeg") == self.img_49x44

    #TODO: Specifiy exception
    @pytest.mark.parametrize("param", [None, "", ",,,", "x,y,w,h"])
    def test_parse_invalid_region_string_raises(self, param):
        with pytest.raises(Exception):
            parse_region_string(param)

    def test_parse_region_string(self):
        assert parse_region_string("-50,-56,100,100") == (-50, -56, 100, 100)
        assert parse_region_string("0,0,50,44") == (0, 0, 50, 44)

    def test_crop_image(self):
        assert crop_image(self.img_96x85, False, "full", "image/jpeg") == self.img_96x85
        assert crop_image(self.img_96x85, False, "0,0,100,100", "image/jpeg") == self.img_96x85
        assert crop_image(self.img_96x85, True, "0,0,50,44", "image/jpeg") == self.img_96x85
        assert crop_image(self.img_96x85, False, "0,0,50,44", "image/jpeg") == self.img_0x0x50x44
        assert crop_image(self.img_96x85, False, "24,24,48,48", "image/jpeg") == self.img_24x24x72x72
        assert crop_image(self.img_96x85, False, "0,41,96,85", "image/jpeg") == self.img_0x41x96x44
        assert crop_image(self.img_96x85, False, "48,0,96,85", "image/jpeg") == self.img_48x0x48x85
        assert crop_image(self.img_96x85, False, "-50,-56,100,100", "image/jpeg") == self.img_0x0x50x44

    #TODO: Specifiy exception
    def test_crop_image_no_size(self):
         with pytest.raises(Exception):
            crop_image(self.img_96x85, False, "0,0,0,0", "image/jpeg")

    #TODO: Specifiy exception
    def test_crop_outside_image(self):
         with pytest.raises(Exception):
            crop_image(self.img_96x85, False, "100,100,50,50", "image/jpeg")