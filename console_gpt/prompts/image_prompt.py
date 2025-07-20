import base64
import os
from typing import Dict, Union

from PIL import Image
from pathlib import Path
from datetime import datetime

from console_gpt.constants import style
from console_gpt.config_manager import IMAGES_PATH
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
        image_path = Path(path_to_image).expanduser()
        Image.open(image_path).verify()
        return True
    except RuntimeError:
        return "Could not determine home directory."
    except FileNotFoundError:
        return f"File not found: {path_to_image}"
    except (IOError, Image.DecompressionBombError):
        return "Not a valid image!"


def _encode_image(image_path) -> str:
    """
    Open an image and convert it to base64 as per OpenAI requirements
    :param image_path: Path to the image
    :return: base64 encoded string
    """
    expanded_path = Path(image_path).expanduser()
    with open(expanded_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def upload_image(model_title) -> Union[Dict, None]:
    """
    Allows uploading multiple images to GPT by converting them to Base64 and encoding them
    :return: None if SIGINT or the whole request body
    """
    openai_model = any(sub in model_title for sub in ("gpt", "o3", "o4"))

    if openai_model:
        images_data = []
        while True:
            image_path = browser_files(
                f"Select an image ({len(images_data)+1}):", "Image selection cancelled.", _is_image
            )
            if not image_path:
                break
            encoded_image = _encode_image(image_path)
            images_data.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{encoded_image}",
            })
            # Ask if user wants to add another image
            add_more = custom_input(
                auto_exit=False,
                message="Add another image? (y/N):",
                style=style,
                qmark="❯",
            )
            if not add_more or add_more.lower() != "y":
                break
        if not images_data:
            return None
        data = images_data
    else:
        image_path = browser_files("Select an image:", "Image selection cancelled.", _is_image)
        if not image_path:
            return None
        encoded_image = _encode_image(image_path)
        if model_title.startswith("anthropic"):
            data = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_image}}
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
    
    if openai_model:
        additional_data = {"type": "input_text", "text": additional_data}
        return additional_data, *data
    else:
        additional_data = {"type": "text", "text": additional_data}
        return additional_data, data

def save_image(image_base64):
    base_name = "image"
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    image_name = f"{base_name}_{timestamp}.png"
    full_path = os.path.join(IMAGES_PATH, image_name)
    with open(full_path, "wb") as file:
        file.write(base64.b64decode(image_base64))
    custom_print("info", f"Successfully saved to - {full_path}")