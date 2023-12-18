import os
from typing import Union, Dict

import questionary

from console_gpt.catch_errors import eof_wrapper
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines, use_emoji_maybe


def _validate_file(val: str) -> Union[str, bool]:
    """
    Supporting function for file_prompt() that verifies
    that the given path leads to a file and not a dir or nothing
    :param val: path to file
    :return: Either True (bool) or an error message
    """
    if os.path.isfile(val):
        return True
    if os.path.isdir(val):
        return "{} is a directory".format(val)
    return "No such file!"


def _read_file(file_path: str) -> Union[str, bool]:
    """
    Read the content of a file
    :param file_path: Path to the file
    :return: The content or None (NoneType) if empty
    """
    with open(file_path, "r") as to_read:
        data = to_read.read()
        not_empty = data.strip()

    return data if not_empty else None


@eof_wrapper
def browser_files(input_message: str, interrupt_message: str, validate_func: object) -> Union[str, None]:
    """
    A base prompt for browsing files
    :param input_message: The prompt message that the user will see
    :param interrupt_message: The message that the user will see upon (SIGINT)
    :param validate_func: The function to use to validate the user input
    :return: Either none if SIGINT or the Path
    """
    custom_style = questionary.Style(
        [
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff"),  # answer color
            ("selected", "fg:#ffffff bg:#000000 bold"),  # selected text color
        ]
    )
    file_name = questionary.path(
        message=input_message, style=custom_style, validate=validate_func, qmark=use_emoji_maybe("\U0001F4C1")
    ).ask()
    if not file_name:
        flush_lines(4)
        custom_print("info", interrupt_message)
        return None
    flush_lines(1)
    return file_name


@eof_wrapper
def file_prompt() -> Union[Dict, None]:
    """
    Prompt for reading content from file.
    :return: The content or None (NoneType)
    """
    file_name = browser_files("Select a file:", "File selection cancelled.", _validate_file)
    if not file_name:
        return None
    data = _read_file(file_name)
    if not data:
        custom_print("info", "The file seems to be empty. Skipping.")
        return None
    return {"role": "user", "content": data}
