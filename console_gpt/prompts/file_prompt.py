import os
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from pypdf import PdfReader
from questionary import path

from console_gpt.catch_errors import eof_wrapper
from console_gpt.constants import custom_style, style
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines, use_emoji_maybe


def _validate_file(file_path: str) -> str | bool:
    """
    Verify if the given path leads to a file and not a directory or non-existe path.
    :param file_path: Path to file
    :return: Either an error message or True represented as string for compatibility
    """
    if os.path.isfile(Path(file_path).expanduser()):
        return True
    if os.path.isdir(Path(file_path).expanduser()):
        return f"{file_path} is a directory"
    return "No such file!"


def _read_file(file_path: str) -> Optional[str]:
    """
    Read the content of a file (TXT or PDF)
    :param file_path: Path to the file
    :return: The content or None if empty or unsupported file type
    """

    expanded_path = str(Path(file_path).expanduser())

    if expanded_path.endswith(".pdf"):
        try:
            with open(expanded_path, "rb") as file:
                pdf_reader = PdfReader(file)
                text = []
                for page in pdf_reader.pages:
                    text.append(page.extract_text())
                content = " ".join(text).strip()
                return content if content else None
        except Exception as e:
            custom_print("error", f"Failed to read PDF file: {e}")
            return None
    elif expanded_path.endswith(".txt"):
        try:
            with open(expanded_path, "r") as file:
                content = file.read().strip()
                return content if content else None
        except Exception as e:
            custom_print("error", f"Failed to read text file: {e}")
            return None
    else:
        custom_print("error", f"Unsupported file type: {expanded_path}")
        return None


@eof_wrapper
def browser_files(input_message: str, interrupt_message: str, validate_func: Callable) -> Optional[str]:
    """
    A base prompt for browsing files
    :param input_message: The prompt message that the user will see
    :param interrupt_message: The message that the user will see upon (SIGINT)
    :param validate_func: The function to use to validate the user input
    :return: Either none if SIGINT or the Path
    """
    file_name = path(
        message=input_message, style=custom_style, validate=validate_func, qmark=use_emoji_maybe("\U0001f4c1")
    ).ask()
    if file_name:
        flush_lines(1)
    else:
        flush_lines(4)
        custom_print("info", interrupt_message)
    return file_name


@eof_wrapper
def file_prompt() -> Tuple[Any, Any]:
    """
    Prompt for reading content from file.
    :return: The content or None (NoneType)
    """
    file_name = browser_files("Select a file:", "File selection cancelled.", _validate_file)
    if not file_name:
        return None, None
    content = _read_file(file_name)
    if not content:
        custom_print("info", "The file seems to be empty. Skipping.")
        return None, None

    additional_data = custom_input(
        auto_exit=False,
        message="Additional clarifications? (Press 'ENTER' to skip):",
        style=style,
        qmark="❯",
    )

    if additional_data:
        return additional_data, f"This is the content of a file:\n{content}"
    else:
        return None, f"This is the content of a file:\n{content}"
