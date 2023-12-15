import json
import os.path
import re
from datetime import datetime
from typing import Dict, List

from questionary import Style

from console_gpt.catch_errors import eof_wrapper
from console_gpt.config_manager import CHATS_PATH, fetch_variable
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print


def _validate_confirmation(val: str):
    """
    Supporting function to save_chat()
    Validates whether the input is correct
    :param val: user input
    :return: True (bool) or error (as text)
    """
    if val.lower() not in ["y", "yes", "n", "no"]:
        return "Please enter either 'y' or 'n'!"
    return True


@eof_wrapper
def save_chat(conversation: List[Dict], ask: bool = False, skip_exit: bool = False) -> None:
    """
    Save chat as a file for later use
    :param conversation: Whole conversation so far
    :param ask: Prompt whether you want to save the chat
    :param skip_exit: Don't exit even if a chat is saved
    :return:
    """
    # Determines if the prompt should be shown
    _show_menu = fetch_variable("features", "save_chat_on_exit")
    # If False the whole code will be skipped
    if not _show_menu:
        if not skip_exit:
            custom_print("exit", "Goodbye, see you soon!", 130)

    style = Style(
        [
            ("qmark", "fg:#ffdb38 bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )
    base_name = "chat"
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    file_name = f"{base_name}_{timestamp}.json"

    prompt_message = (
        f"Please provide a file name to save the chat.\n" f"╰─❯ Press 'ENTER' for the default name ({file_name}):"
    )
    # First Question
    user_agreement = (
        custom_input(
            message="Would you like to save the current chat? (Y/N):",
            qmark="❯",
            style=style,
            validate=_validate_confirmation,
        )
        if ask
        else "y"
    )  # PAY ATTENTION HERE

    # Second Question
    if user_agreement in ["y", "yes"]:
        chat_name = custom_input(
            is_single_line=False,
            message=prompt_message,
            qmark="╭─",
            style=style,
        )
        chat_name = file_name if chat_name == "" else chat_name
        chat_name = re.sub(r"(\t|\s|\n)+", "_", chat_name)
        chat_name = chat_name if chat_name.endswith(".json") else chat_name + ".json"
        full_path = os.path.join(CHATS_PATH, chat_name)
        with open(full_path, "w", encoding="utf-8") as file:
            json.dump(conversation, file, indent=4, ensure_ascii=False)
        custom_print("info", f"Successfully saved to - {full_path}", (None if skip_exit else 0))
    else:
        if not skip_exit:
            custom_print("exit", "Goodbye, see you soon!", 130)
