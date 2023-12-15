from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from questionary import Style
from typing import Union, Dict
from console_gpt.catch_errors import eof_wrapper


def _validate_description(val: str) -> Union[str, bool]:
    """
    Sub-function to _add_custom_role() which validates
    the user input and does not allow empty values
    :param val: The STDIN from the user
    :return: Either error string or bool to confirm that
    the user input is valid
    """
    if not val or val.startswith(" "):
        return "Empty input not allowed!"
    return True


@eof_wrapper
def multiline_prompt() -> Union[Dict, None]:
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
        custom_print('info', 'Cancelled. Continuing normally!')
        return None

    additional_data = custom_input(
        auto_exit=False,
        message="Additional clarifications? (Please 'ENTER' to skip):",
        style=style,
        qmark="❯",
    )
    user_input = additional_data + "\n" + multiline_data
    return {"role": "user", "content": user_input}
