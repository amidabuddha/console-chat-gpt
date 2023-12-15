from typing import Union

from questionary import Style

from console_gpt.catch_errors import eof_wrapper
from console_gpt.config_manager import fetch_variable
from console_gpt.custom_stdin import custom_input


def _validate_temp(val: str) -> Union[str, bool]:
    """
    Sub-function to temperature_prompt() to validate user input.
    The function allows only `2 >= val >= 0`
    :param val: User input
    :return: True (bool) or an error (text)
    """
    if not val:
        return True
    try:
        val = float(val)
        return True if 2 >= val >= 0 else "Enter a number between 0 and 2!"
    except ValueError:
        return "Enter a number!"


@eof_wrapper  # Wrapper to handle CTRL+D (EOFError)
def temperature_prompt() -> Union[float, int]:
    """
    Handles the chat temperature (randomness).
    """
    _show_menu = fetch_variable("features", "adjust_temperature")
    default_temperature = fetch_variable("defaults", "temperature")
    if not _show_menu:
        return default_temperature

    style = Style(
        [
            ("qmark", "fg:#ffdb38 bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )
    prompt_message = (
        f"Enter a value between 0 and 2 to define GPT randomness.\n"
        f"╰─❯ Press 'ENTER' for the default setting ({default_temperature}):"
    )
    user_input = custom_input(
        message=prompt_message,
        qmark="╭─",
        validate=_validate_temp,
        style=style,
    )
    return user_input if user_input else default_temperature
