import json
import os
from typing import Dict, List, Optional

from console_gpt.config_manager import CHATS_PATH, fetch_variable
from console_gpt.custom_stdout import colored, custom_print
from console_gpt.general_utils import flush_lines
from console_gpt.menus.skeleton_menus import base_multiselect_menu

"""
Select chat to continue
"""


def _read_old_chat(chat_name: str, already_failed=False) -> Optional[List[Dict]]:
    """
    Supporting function for select_chat_menu().
    This will extract and verify the content of the JSON file
    :param chat_name: the name of the chat file
    :param already_failed: Used to catch if the user generated an error 1+ times
    :return: The content of the file or start the menu again.
    """
    full_path = os.path.join(CHATS_PATH, chat_name)
    try:
        with open(full_path, "r") as file:
            data = json.load(file)
            # Automatically flush the error message on successful loading
            flush_lines((3 if already_failed else 0))
            custom_print("ok", f"Successfully loaded previous chat - {chat_name}")
        return data
    except json.JSONDecodeError as e:
        arrow = colored("╰─❯", "red")
        # Automatically flush the error if repeated
        flush_lines((3 if already_failed else 0))
        custom_print("error", f"Failed to load previous chat due to error:\n {arrow} {e}")
        custom_print("info", "Select another chat or Skip.")
        return select_chat_menu(True)


def select_chat_menu(already_failed=False) -> Optional[List[Dict]]:
    """
    Generates a menu to select a previous chat in order
    to continue from where you left
    :param already_failed: Used to catch if the user generated an error 1+ times
    :return: The selected conversion
    """
    _show_menu = fetch_variable("features", "continue_chat")
    menu_data = os.listdir(CHATS_PATH)
    if not len(menu_data) or not _show_menu:
        return None
    extensionless_data = [x.removesuffix(".json") for x in menu_data]
    manu_title = "Continue an old chat?:"
    selection = base_multiselect_menu(extensionless_data, manu_title, 0, True)
    if selection == "Skip":
        return None
    return _read_old_chat(menu_data[extensionless_data.index(selection) - 1], already_failed)
