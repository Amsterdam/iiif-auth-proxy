import logging
from io import BytesIO

from django.http import HttpResponse
from PIL import Image

from iiif import tools

log = logging.getLogger(__name__)

MALFORMED_SCALING_PARAMETER = "The scaling parameter is malformed. It should either be 'full' or in the form of '100,50'."

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

        desired_width = int(parts[0]) if parts[0] else None
        desired_height = int(parts[1]) if parts[1] else None
    except ValueError as e:
        raise tools.ImmediateHttpResponse(response=HttpResponse(MALFORMED_SCALING_PARAMETER, status=400))

    return desired_width, desired_height


def scale_image(content, scaling, content_type):
    """
    Scale the image to the desired size. Never scale up.

    :param content: The image data
    :param scaling: The scaling string from the url
    :param content_type: The content type of the image
    :return: The scaled image data
    """
    if scaling.lower() == "full":
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
    format = content_type.split("/")[1].upper()
    scaled_image.save(image_stream, format=format)
    scaled_image_data = image_stream.getvalue()

    return scaled_image_data
