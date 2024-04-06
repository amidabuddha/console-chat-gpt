import os
from typing import Callable, Optional

from questionary import Style, path

from console_gpt.catch_errors import eof_wrapper
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines, use_emoji_maybe


def _validate_file(file_path: str) -> str | bool:
    """
    Verify if the given path leads to a file and not a directory or non-existe path.
    :param file_path: Path to file
    :return: Either an error message or True represented as string for compatibility
    """
    if os.path.isfile(file_path):
        return True
    if os.path.isdir(file_path):
        return f"{file_path} is a directory"
    return "No such file!"


def _read_file(file_path: str) -> Optional[str]:
    """
    Read the content of a file
    :param file_path: Path to the file
    :return: The content or None (NoneType) if empty
    """
    with open(file_path, "r") as file:
        content = file.read().strip()

    return content if content else None


@eof_wrapper
def browser_files(input_message: str, interrupt_message: str, validate_func: Callable[[str], str]) -> Optional[str]:
    """
    A base prompt for browsing files
    :param input_message: The prompt message that the user will see
    :param interrupt_message: The message that the user will see upon (SIGINT)
    :param validate_func: The function to use to validate the user input
    :return: Either none if SIGINT or the Path
    """
    custom_style = Style(
        [
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff"),  # answer color
            ("selected", "fg:#ffffff bg:#000000 bold"),  # selected text color
        ]
    )
    file_name = path(
        message=input_message, style=custom_style, validate=validate_func, qmark=use_emoji_maybe("\U0001F4C1")
    ).ask()
    if file_name:
        flush_lines(1)
    else:
        flush_lines(4)
        custom_print("info", interrupt_message)
    return file_name


@eof_wrapper
def file_prompt() -> Optional[str]:
    """
    Prompt for reading content from file.
    :return: The content or None (NoneType)
    """
    file_name = browser_files("Select a file:", "File selection cancelled.", _validate_file)
    if not file_name:
        return None
    content = _read_file(file_name)
    if not content:
        custom_print("info", "The file seems to be empty. Skipping.")
        return None

    style = Style(
        [
            ("qmark", "fg:#86cdfc bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )

    additional_data = custom_input(
        auto_exit=False,
        message="Additional clarifications? (Press 'ENTER' to skip):",
        style=style,
        qmark="❯",
    )
    if additional_data:
        content = additional_data + ":\n" + content
    return content
