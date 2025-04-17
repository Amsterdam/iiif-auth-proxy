import json
import logging
from copy import deepcopy
from io import BytesIO

from django.http import HttpResponse
from PIL import Image

from main import utils
from main.utils import clamp

# Allow larger images too be processed. We can do this because we trust the source of the images
Image.MAX_IMAGE_PIXELS = None

log = logging.getLogger(__name__)

MALFORMED_SCALING_PARAMETER = "The scaling parameter is malformed. It should either be 'full' or in the form of '100,50'."
MISSING_SCALING_PARAMETER = "The scaling parameter is missing. It should either be 'full' or in the form of '100,50'."
MALFORMED_REGION_PARAMETER = "The region parameter is malformed. It should either be 'full' or in the form of '50,50,100,100' (x,y,w,h)."
MISSING_REGION_PARAMETER = "The region parameter is missing. It should either be 'full' or in the form of '50,50,100,100' (x,y,w,h)."
NON_OVERLAPPING_REGION_PARAMETER = "The region parameter should overlap with the image."
NON_POSITIVE_WIDTH_HEIGHT_REGION_PARAMETER = (
    "The region parameter should have a positive width and height value"
)

BASE_INFO_JSON = {
    "@context": "http://iiif.io/api/image/2/context.json",
    "@id": None,
    "protocol": "http://iiif.io/api/image",
    "width": None,
    "height": None,
    "sizes": [{"width": None, "height": None}],
    "profile": [
        "http://iiif.io/api/image/2/level2.json",
        {
            "formats": [],
            "qualities": ["default"],
            "supports": ["sizeByW", "sizeByH", "sizeByWh", "regionByPx"],
        },
    ],
}


def generate_info_json(image_base_url, content, content_type):
    """
    Generate the info.json for the image

    :param image_base_url: The base url of the image
    :param content: The image data
    :param content_type: The content type of the image
    :return: The info.json
    """
    img = Image.open(BytesIO(content))

    info_json = deepcopy(BASE_INFO_JSON)
    info_json["@id"] = image_base_url
    info_json["width"] = img.width
    info_json["height"] = img.height
    info_json["sizes"] = [{"width": img.width, "height": img.height}]
    info_json["profile"][1]["formats"] = [
        content_type_to_format(content_type).replace("jpeg", "jpg")
    ]

    return json.dumps(info_json)


def parse_scaling_string(scaling):
    """
    Parse the scaling string from the url (either 'full' or '100,50' in which
    100=max width and 50=max height)

    :param scaling: The scaling string from the url
    :return: Tuple containing the max width and max height
    """
    try:
        parts = scaling.split(",")
        if len(parts) != 2:
            raise ValueError("Invalid format for scaling")

        if not (parts[0] or parts[1]):
            raise ValueError(
                "Invalid format for scaling. Width or height value required."
            )

        requested_width = int(parts[0]) if parts[0] else None
        requested_height = int(parts[1]) if parts[1] else None
    except ValueError as e:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MALFORMED_SCALING_PARAMETER, status=400)
        ) from e
    except AttributeError as e:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MISSING_SCALING_PARAMETER, status=400)
        ) from e

    return requested_width, requested_height


def is_image_content_type(content_type):
    return content_type.split("/")[0] == "image"


def content_type_to_format(content_type):
    return content_type.split("/")[1]


def calculate_scaled_dimensions(img, requested_width, requested_height):
    aspect_ratio = img.width / img.height
    if requested_width is None:
        width = int(requested_height * aspect_ratio)
        height = requested_height
        return width, height

    if requested_height is None:
        width = requested_width
        height = int(requested_width / aspect_ratio)
        return width, height

    width_reduction_percentage = (img.width - requested_width) / img.width
    height_reduction_percentage = (img.height - requested_height) / img.height

    if width_reduction_percentage >= height_reduction_percentage:
        width = requested_width
        height = int(requested_width / aspect_ratio)
    else:
        width = int(requested_height * aspect_ratio)
        height = requested_height
    return width, height


def scale_image(content_type, scaling, content):
    """
    Scale the image to the requested size. Never scale up.

    :param content: The image data
    :param scaling: The scaling string from the url
    :param content_type: The content type of the image
    :return: The scaled image data
    """
    if scaling.lower() == "full":
        return content

    img = Image.open(BytesIO(content))
    requested_width, requested_height = parse_scaling_string(scaling)
    target_width, target_height = calculate_scaled_dimensions(
        img, requested_width, requested_height
    )

    # Ensure we don't scale up
    if target_width > img.width or target_height > img.height:
        return content

    image_stream = BytesIO()
    image_format = content_type_to_format(content_type)
    scaled_image = img.resize((target_width, target_height), Image.LANCZOS)
    scaled_image.save(image_stream, format=image_format)
    scaled_image_data = image_stream.getvalue()

    return scaled_image_data


# TODO: Support percentage string: pct:x,y,w,h
def parse_region_string(region):
    """
    Parse the region string from the url (either 'full', 'square' or 'x,y,w,h' in pixels)

    :param region: The region string from the url
    :return: Tuple containing the requested x, y, width and height.
    """
    try:
        parts = region.split(",")
        if len(parts) != 4:
            raise ValueError("Invalid format for region")

        if not (parts[0] and parts[1] and parts[2] and parts[3]):
            raise ValueError(
                "Invalid format for region. x, y, width and height values required."
            )

        requested_x = int(parts[0])
        requested_y = int(parts[1])
        requested_width = int(parts[2])
        requested_height = int(parts[3])
    except ValueError as e:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MALFORMED_REGION_PARAMETER, status=400)
        ) from e
    except AttributeError as e:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MISSING_REGION_PARAMETER, status=400)
        ) from e

    return requested_x, requested_y, requested_width, requested_height


def assert_valid_region(
    img, requested_x, requested_y, requested_width, requested_height
):
    region_has_no_width = requested_width <= 0 or requested_width is None
    region_has_no_height = requested_height <= 0 or requested_height is None
    if region_has_no_width or region_has_no_height:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(
                NON_POSITIVE_WIDTH_HEIGHT_REGION_PARAMETER, status=400
            )
        )

    region_has_no_overlap_with_img = (
        requested_x + requested_width <= 0
        or requested_y + requested_height <= 0
        or requested_x >= img.width
        or requested_y >= img.height
    )
    if region_has_no_overlap_with_img:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(NON_OVERLAPPING_REGION_PARAMETER, status=400)
        )


# TODO: Extract sub functions to own functions for:
# - asserting the region is valid
# - return original when no crop was applied
def crop_image(content_type, region, content):
    """
    Crop the image to the requested size. Never crop outside the image.

    :param content: The image data
    :param source_file: Bool whether the raw source file should be returned without any cropping
    :param region: The region string from the url
    :param content_type: The content type of the image
    :return: The cropped image data
    """
    img = Image.open(BytesIO(content))

    match region.lower():
        case "full":
            return content
        case "square":
            shortest_side = min(img.width, img.height)
            requested_width = requested_height = shortest_side
            requested_x = (img.width - requested_width) / 2
            requested_y = (img.height - requested_height) / 2
        case _:
            requested_x, requested_y, requested_width, requested_height = (
                parse_region_string(region)
            )

    assert_valid_region(
        img, requested_x, requested_y, requested_width, requested_height
    )

    left = clamp(requested_x, 0, img.width)
    top = clamp(requested_y, 0, img.height)
    right = clamp(requested_x + requested_width, left, img.width)
    bottom = clamp(requested_y + requested_height, top, img.height)

    crop_contains_complete_img = (
        left <= 0 and top <= 0 and right >= img.width and bottom >= img.height
    )
    if crop_contains_complete_img:
        return content

    image_stream = BytesIO()
    image_format = content_type_to_format(content_type)
    cropped_image = img.crop((left, top, right, bottom))
    cropped_image.save(image_stream, format=image_format)
    cropped_image_data = image_stream.getvalue()

    return cropped_image_data
