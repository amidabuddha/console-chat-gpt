from typing import Dict

from console_gpt.config_manager import fetch_variable, write_to_config
from console_gpt.menus.skeleton_menus import base_settings_menu
from console_gpt.prompts.system_prompt import system_reply


def _write_wrapper(data: Dict) -> None:
    """
    Wrapper for the write_to_config function which breaks down dict into key:value
    Where key is the config entry and value is the new value of that entry
    :param data: Dict data from the base_settings_menu()
    :return: Nothing, just writes
    """
    for key, value in data.items():
        write_to_config("features", key, new_value=value)


def _table_wrapper(col1, col2, col3):
    """
    Create table row
    :param col1: first column
    :param col2: second column
    :param col3: third column
    :return: return a single table row
    """
    return f"|{col1}|{col2}|{col3}"


def _generate_markdown_reply(data: Dict) -> str:
    """
    Create a Markdown table reply based on key:value pairs
    :param data:
    :return:
    """
    header = """
| Entry      | New Value | Old Value|
| :---        |    :----:   |          ---: |
"""
    table = "\n".join([_table_wrapper(x, y, not bool(y)) for x, y in data.items()])
    return header + table


def settings_menu() -> None:
    """
    Allows managing the existing chat features
    :return: Nothing
    """
    menu_data = fetch_variable("features")
    menu_title = " Control Features"
    selection = base_settings_menu(menu_data, menu_title)
    _write_wrapper(selection)
    if menu_data != selection:
        system_reply(_generate_markdown_reply(selection))
    else:
        system_reply("No new changes!")
