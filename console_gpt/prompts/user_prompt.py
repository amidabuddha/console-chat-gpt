from typing import Dict, Union

import questionary

from console_gpt.catch_errors import eof_wrapper
from console_gpt.general_utils import flush_lines, use_emoji_maybe


@eof_wrapper
def user_prompt() -> str:
    """
    User chat prompt during the session
    :return: User input as string
    """
    custom_style = questionary.Style(
        [
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff"),  # answer color
            ("selected", "fg:#ffffff bg:#000000 bold"),  # selected text color
        ]
    )

    option_description = {
        "help": "Prints all available commands.",
        "cost": "Prints the costs of the current chat.",
        "edit": "Prints the last prompt so you can edit it.",
        "exit": "Exits the chat.",
        "file": "Allows you to upload the content of a file to the chat.",
        "image": "Allows you to upload an image (Supported by gpt-4-vision-preview only).",
        "flush": "Start the chat all over again.",
        "format": "Allows you to write multiline messages.",
        "save": "Saves the chat to a given file.",
        "settings": "Manage available features.",
    }

    prompt_title = "User:"
    options = ["help", "cost", "edit", "exit", "file", "image", "flush", "format", "save", "settings"]
    user_input = questionary.autocomplete(
        message=prompt_title,
        choices=options,
        qmark=use_emoji_maybe("\U0001F9D1"),
        meta_information=option_description,
        style=custom_style,
        validate=lambda x: True if x and not x.isspace() else "Empty inputs are not allowed!",
    ).ask()
    return user_input

def chat_user_prompt() -> Union[Dict, None]:
    """
    Returns user prompt in expected format by the chat API
    :return: Dictionary format to be added to the list of messages for the chat completon API or None
    """
    user_input = user_prompt()
    # flush_lines will remove the default lines set by the library
    return {"role": "user", "content": user_input} if user_input else flush_lines(3)

def assistant_user_prompt() -> str:
    """
    Returns user prompt in expected format by the assistant API
    :return: string to be nested into the thread as content
    """
    user_input = user_prompt()
    # flush_lines will remove the default lines set by the library
    return user_input if user_input else flush_lines(3)