import os
import json
import shutil

from console_gpt.config_manager import CHATS_PATH
from console_gpt.menus.skeleton_menus import base_multiselect_menu, base_checkbox_menu
from console_gpt.prompts.system_prompt import system_reply
from console_gpt.custom_stdout import custom_print
from console_gpt.custom_stdin import custom_input
from console_gpt.prompts.file_prompt import browser_files
from console_gpt.constants import style
from typing import Union

"""
Chat management
"""

def _chat_exists(path_to_file: str) -> Union[str, bool]:
    """
    Verify if a chat with the same name already exists
    :param path_to_file: Path to file
    :return: Either an error message or True represented as string for compatibility
    """
    if path_to_file.endswith('.json'):
        if os.path.exists(os.path.join(CHATS_PATH, path_to_file)):
            return f"Chat with the name {path_to_file.strip('.json')} already exists!"
    else:
        if os.path.exists(os.path.join(CHATS_PATH, f"{path_to_file}.json")):
            return f"Chat with the name {path_to_file} already exists!"
    return True

def _is_chat(path_to_file: str) -> Union[str, bool]:
    """
    Verify if the given path leads to a valid chat and not a directory or non-existing path
    :param path_to_file: Path to file
    :return: Either an error message or True represented as string for compatibility
    """
    if os.path.isfile(path_to_file):
        try:
            with open(path_to_file, 'r') as file:
                _ = json.load(file)
            return True
        except json.JSONDecodeError as e:
            return f"Unable to parse chat due to: {str(e)}"
    if os.path.isdir(path_to_file):
        return f"{path_to_file} is a directory!"
    return "No such file!"

def _import_chats() -> None:
    """
    Import existing chat by copying it into the `chats` directory
    Does basic verification and doesn't modify the original file
    """
    custom_print("info", "Please note that this will only copy the file to the chats directory, no changes will be done to the original file!")

    chat_path = browser_files("Select chat:", "Chat selection cancelled", _is_chat)
    if not chat_path:
        system_reply("No chat selected.")
        return None

    copy_filename = os.path.basename(chat_path)
    if os.path.exists(os.path.join(CHATS_PATH, copy_filename)):
        custom_print("error", f"Can't import {copy_filename} since a chat with the same name already exists!")
        copy_filename = custom_input(
            message="Select a new name for the chat:",
            qmark="❯",
            style=style,
            validate=_chat_exists,
        )
    
    # Handle just in case, since `custom_input` can return None
    if copy_filename is None:
        system_reply("No chat selected.")
        return None
    
    if not copy_filename.endswith('.json'):
        copy_filename = copy_filename + '.json'

    shutil.copy2(chat_path, os.path.join(CHATS_PATH, copy_filename))
    custom_print("ok", f"Chat {copy_filename} successfully imported!")

def _delete_chats() -> None:
    """
    Detect and delete existing chats, allows for selecting multiple ones at once.
    Simply removes the file from the `chats` directory
    """
    available_chats = os.listdir(CHATS_PATH)
    if len(available_chats) == 0:
        system_reply("No available chats!")
        return None

    chats_selection = base_checkbox_menu(available_chats, "Select which chats to delete:")
    if not chats_selection:
        system_reply("No chat selected.")
        return None

    for chat in chats_selection:
        os.remove(os.path.join(CHATS_PATH, chat))
        custom_print("ok", f"Successfully deleted chat - {chat}")


def chat_manager() -> None:
    selection = base_multiselect_menu(
        menu_name="Chat Manager Actions:",
        data=[
            "Sync External Chat",
            "Delete",
            "Return"
        ],
        menu_title="Select an action:",
        exit=False
    )

    match selection:
        case "Sync External Chat":
            _import_chats()
        case "Delete":
            _delete_chats()
        case "Return":
            system_reply("No actions performed!")
            return None
