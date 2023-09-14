from iiif.image_handling import parse_scaling_string, scale_image


class TestImageFormatting:
    def setup_method(self):
        with open("test-images/test-image-96x85.jpg", "rb") as f:
            self.img_96x85 = f.read()  # 96x85
        with open("test-images/test-image-50x44.jpg", "rb") as f:
            self.img_50x44 = f.read()
        with open("test-images/test-image-49x44.jpg", "rb") as f:
            self.img_49x44 = f.read()

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
