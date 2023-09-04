import logging

from django.http import HttpResponse

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

def scale_image(content, scaling, format):
    """
    Resize an image from given content.

    :param content: The content of the image (usually response.content from requests)
    :param scaling: The scaling string from the url (either 'full' or '100,50' in which 
                    100=max width and 50=max height)
    :return: Scaled image
    """
    if scaling.lower() == "full":
        return content

    # TODO: The cod below is WIP
    # desired_width, desired_height = parse_scaling_string(scaling)
    #
    # img = Image.open(BytesIO(content))
    #
    # aspect_ratio = img.width / img.height
    # if aspect_ratio > 1:
    #     new_width = desired_width
    #     new_height = int(desired_width / aspect_ratio)
    # elif aspect_ratio < 1:
    #     new_width = int(desired_height * aspect_ratio)
    #     new_height = desired_height
    # else:
    #     new_width = desired_width
    #     new_height = desired_height
    #
    # scaled_image = img.resize((new_width, new_height), Image.LANCZOS)
    #
    # image_stream = BytesIO()
    # scaled_image.save(image_stream, format=format)
    # scaled_image_data = image_stream.getvalue()
    #
    # return scaled_image_data
