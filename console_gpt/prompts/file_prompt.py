import questionary
from typing import Union
import os
from console_gpt.catch_errors import eof_wrapper
from console_gpt.general_utils import use_emoji_maybe, flush_lines
from console_gpt.custom_stdout import custom_print


def _validate_file(val: str) -> Union[str, bool]:
    if os.path.isfile(val):
        return True
    if os.path.isdir(val):
        return "{} is a directory".format(val)
    return "No such file!"


def _read_file(file_path: str) -> Union[str, bool]:
    with open(file_path, 'r') as to_read:
        data = to_read.read()
        not_empty = data.strip()

    return data if not_empty else None


@eof_wrapper
def file_prompt():
    custom_style = questionary.Style(
        [
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff"),  # answer color
            ("selected", "fg:#ffffff bg:#000000 bold"),  # selected text color
        ]
    )
    file_name = questionary.path(
        message="Select a file:",
        style=custom_style,
        validate=_validate_file,
        qmark=use_emoji_maybe("\U0001F4C1")
    ).ask()
    if not file_name:
        flush_lines(4)
        custom_print('info', "File selection cancelled.")
        return None

    data = _read_file(file_name)
    if not data:
        custom_print('info', 'The file seems to be empty. Skipping.')
        return None
    return {"role": "user", "content": data}
