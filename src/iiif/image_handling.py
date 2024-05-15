import json
import logging
from copy import deepcopy
from io import BytesIO

from django.http import HttpResponse
from PIL import Image

from main import utils

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

        desired_width = int(parts[0]) if parts[0] else None
        desired_height = int(parts[1]) if parts[1] else None
    except ValueError:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MALFORMED_SCALING_PARAMETER, status=400)
        )
    except AttributeError:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MISSING_SCALING_PARAMETER, status=400)
        )

    return desired_width, desired_height


def content_type_to_format(content_type):
    return content_type.split("/")[1]


def scale_image(source_file, content_type, scaling, content):
    """
    Scale the image to the desired size. Never scale up.

    :param content: The image data
    :param source_file: Bool whether the raw source file should be returned without any scaling
    :param scaling: The scaling string from the url
    :param content_type: The content type of the image
    :return: The scaled image data
    """
    if source_file or scaling.lower() == "full":
        return content

    desired_width, desired_height = parse_scaling_string(scaling)

    img = Image.open(BytesIO(content))

    aspect_ratio = img.width / img.height
    if desired_width is None:
        new_width = int(desired_height * aspect_ratio)
        new_height = desired_height
    elif desired_height is None:
        new_width = desired_width
        new_height = int(desired_width / aspect_ratio)
    else:
        width_reduction_percentage = (img.width - desired_width) / img.width
        height_reduction_percentage = (img.height - desired_height) / img.height

        if width_reduction_percentage >= height_reduction_percentage:
            new_width = desired_width
            new_height = int(desired_width / aspect_ratio)
        else:
            new_width = int(desired_height * aspect_ratio)
            new_height = desired_height

    # Ensure we don't scale up
    if new_width > img.width or new_height > img.height:
        return content

    scaled_image = img.resize((new_width, new_height), Image.LANCZOS)

    image_stream = BytesIO()
    format = content_type_to_format(content_type)
    scaled_image.save(image_stream, format=format)
    scaled_image_data = image_stream.getvalue()

    return scaled_image_data


# TODO: Support percentage string: pct:x,y,w,h
def parse_region_string(region):
    """
    Parse the region string from the url (either 'full', 'square' or 'x,y,w,h' in pixels)

    :param region: The region string from the url
    :return: Tuple containing the desired x, y, width and height.
    """
    try:
        parts = region.split(",")
        if len(parts) != 4:
            raise ValueError("Invalid format for region")

        if not (parts[0] and parts[1] and parts[2] and parts[3]):
            raise ValueError(
                "Invalid format for region. x, y, width and height values required."
            )

        desired_x = int(parts[0])
        desired_y = int(parts[1])
        desired_width = int(parts[2])
        desired_height = int(parts[3])
    except ValueError:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MALFORMED_REGION_PARAMETER, status=400)
        )
    except AttributeError:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(MISSING_REGION_PARAMETER, status=400)
        )

    return desired_x, desired_y, desired_width, desired_height


# TODO: Move to an util file
def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)


# TODO: Extract sub functions to own functions for:
# - asserting the region is valid
# - return original when no crop was applied
def crop_image(source_file, content_type, region, content):
    """
    Crop the image to the desired size. Never crop outside the image.

    :param content: The image data
    :param source_file: Bool whether the raw source file should be returned without any cropping
    :param region: The region string from the url
    :param content_type: The content type of the image
    :return: The cropped image data
    """
    if source_file:
        return content

    img = Image.open(BytesIO(content))

    match region.lower():
        case "full":
            return content
        case "square":
            shortest_side = min(img.width, img.height)
            desired_width = desired_height = shortest_side
            desired_x = (img.width - desired_width) / 2
            desired_y = (img.height - desired_height) / 2
        case _:
            desired_x, desired_y, desired_width, desired_height = parse_region_string(
                region
            )

    region_has_no_width = desired_width <= 0 or desired_width == None
    region_has_no_height = desired_height <= 0 or desired_height == None
    if region_has_no_width or region_has_no_height:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(
                NON_POSITIVE_WIDTH_HEIGHT_REGION_PARAMETER, status=400
            )
        )

    region_has_no_overlap_with_img = (
        desired_x + desired_width <= 0
        or desired_y + desired_height <= 0
        or desired_x >= img.width
        or desired_y >= img.height
    )
    if region_has_no_overlap_with_img:
        raise utils.ImmediateHttpResponse(
            response=HttpResponse(NON_OVERLAPPING_REGION_PARAMETER, status=400)
        )

    left = clamp(desired_x, 0, img.width)
    top = clamp(desired_y, 0, img.height)
    right = clamp(desired_x + desired_width, left, img.width)
    bottom = clamp(desired_y + desired_height, top, img.height)

    crop_contains_complete_img = (
        left <= 0 and top <= 0 and right >= img.width and bottom >= img.height
    )

    if crop_contains_complete_img:
        return content

    cropped_image = img.crop((left, top, right, bottom))

    image_stream = BytesIO()
    format = content_type_to_format(content_type)
    cropped_image.save(image_stream, format=format)
    cropped_image_data = image_stream.getvalue()

    return cropped_image_data
