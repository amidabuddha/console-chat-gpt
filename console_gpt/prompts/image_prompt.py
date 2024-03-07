import base64
from typing import Dict, Union

from PIL import Image
from questionary import Style

from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from console_gpt.prompts.file_prompt import browser_files


def _is_image(path_to_image: str) -> Union[bool, str]:
    """
    Checks if the given file as an actual image.
    :param path_to_image: Path to the image
    :return: Either True or an Error
    """
    if not path_to_image:
        return "Specify a path!"
    try:
        Image.open(path_to_image)
        return True
    except (IOError, Image.DecompressionBombError):
        return "Not a valid image!"


def _encode_image(image_path) -> str:
    """
    Open an image and convert it to base64 as per OpenAI requirements
    :param image_path: Path to the image
    :return: base64 encoded string
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def upload_image(model_title) -> Union[Dict, None]:
    """
    Allows uploading images to GPT by converting them to Base64 and encode them
    :return: None if SIGINT or the whole request body
    """
    image_path = browser_files("Select an image:", "Image selection cancelled.", _is_image)
    if not image_path:
        return None

    style = Style(
        [
            ("qmark", "fg:#86cdfc bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )
    encoded_image = _encode_image(image_path)

    if model_title == "anthropic":
        data = {
            "type": "image", "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": encoded_image
                }
            }
    else:
        data = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
        }

    additional_data = custom_input(
        auto_exit=False,
        message="Additional clarifications? (Press 'ENTER' to skip):",
        style=style,
        qmark="❯",
    )

    if additional_data is None:
        custom_print("info", "Cancelled. Continuing normally!")
        return None
    additional_data = {"type": "text", "text": additional_data}

    return additional_data, data
