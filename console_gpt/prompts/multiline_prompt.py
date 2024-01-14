import re
from typing import Dict, Optional

from questionary import Style

from console_gpt.catch_errors import eof_wrapper
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print

# Compile the regex once at the module level
stop_regex = re.compile(r"(\n|\s)+$") 

def _validate_description(val: str) -> str|bool:
    """
    Sub-function to _add_custom_role() which validates
    the user input and does not allow empty values
    :param val: The STDIN from the user
    :return: Either error string or bool to confirm that
    the user input is valid
    """
    if not val or stop_regex.match(val):
        return "Empty input not allowed!"
    return True


@eof_wrapper
def multiline_prompt() -> Optional[str]:
    """
    Multiline prompt which allows writing on multiple lines without
    "Enter" (Return) interrupting your input.
    :return: The content or None (If cancelled)
    """
    style = Style(
        [
            ("qmark", "fg:#86cdfc bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )
    multiline_data = custom_input(
        is_single_line=False,
        auto_exit=False,
        message="Multiline input",
        style=style,
        qmark="❯",
        validate=_validate_description,
        multiline=True,
    )
    if not multiline_data:
        custom_print("info", "Cancelled. Continuing normally!")
        return None

    additional_data = custom_input(
        auto_exit=False,
        message="Additional clarifications? (Press 'ENTER' to skip):",
        style=style,
        qmark="❯",
    )
    return f"{additional_data}:\n{multiline_data}" if additional_data else multiline_data 
