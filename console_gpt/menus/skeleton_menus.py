from typing import Callable, Dict, List, Optional, Union

import questionary
from simple_term_menu import TerminalMenu

from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines, use_emoji_maybe


def base_multiselect_menu(
    menu_name: str,
    data: List[str],
    menu_title: str,
    default_value: Optional[Union[int, str]] = 0,
    skip_option: bool = False,
    show_search: bool = False,
    preview_command: Optional[Callable] = None,
    preview_size: float = 0.25,
    preview_title: str = "preview",
    exit: bool = True,
    exit_message: str = "Goodbye! See you later!",
) -> Union[str, None]:
    """
    Creates a multiselect menu

    :param menu_name: The name of the menu so we can have more accurate errors
    :param data: The data you would like to be used in the menu
    :param menu_title: The title to be displayed on top of the menu
    :param default_value: Either the index or the name of the default value to be displayed first
    :param skip_option: Weather to have a skip button on top or not
    :param show_search: Shows an info message about the search at the bottom
    :param preview_title: Preview title to be displayed
    :param preview_size: Box width and height of the preview
    :param preview_command: Function used to generate a preview
    :param exit: Allows the user to quit the appication from this menu
    :param exit_message: Message to display to the user before exiting
    :return: Exits upon ctrl+c and the given keys, otherwise returns the item from the menu
    """
    menu_title = f"(Press Q or Esc to exit)\n\n{menu_title}"
    if isinstance(default_value, int):
        data_size = len(data) if skip_option else len(data) - 1
        if default_value > data_size:
            custom_print("error", f"Invalid default value at {menu_name}!", exit_code=1)
    elif isinstance(default_value, str):
        if default_value not in data:
            custom_print("error", f"Invalid default value at {menu_name}!", exit_code=1)
        default_value = data.index(default_value)
    else:
        custom_print("error", f"Invalid default value data type at {menu_name}!", exit_code=1)

    if skip_option:
        data.insert(0, "Skip")

    # Adding Exit button at the end
    if exit:
        data.append("Exit")

    terminal_menu = TerminalMenu(
        data,
        cursor_index=default_value,
        title=menu_title,
        skip_empty_entries=True,
        show_search_hint=show_search,
        menu_cursor="» ",
        preview_command=preview_command,
        preview_size=preview_size,
        preview_title=preview_title,
    )
    menu_entry_index = terminal_menu.show()
    # Catching SIGINT by checking the return of the previous function (None)
    selection = "Exit" if menu_entry_index is None else data[menu_entry_index]
    return selection if selection != "Exit" else custom_print("exit", exit_message, 0)


def base_settings_menu(data: Dict[str, bool], menu_title: Optional[str] = "Settings:") -> Dict[str, bool]:
    """
    Displays the settings menu which is toggleable on the console
    :param data: The existing values from the config.toml
    :param menu_title: The title of the menu
    :return:
    """
    result = {}
    label_length = max(len(k) for k, v in data.items()) + 2
    menu_data = [f"{k.replace('_', ' ').title():<{label_length}}| {v}" for k, v in data.items()]
    selections = questionary.checkbox(menu_title, choices=menu_data, qmark=use_emoji_maybe("\u2699\ufe0f")).ask()
    flush_lines()  # Used to flush the original output of the library

    if selections in [None, []]:
        # If nothing is selected or ctrl+c
        # Return the original data
        flush_lines(3) if selections is None else flush_lines(0)
        return data

    for selection in selections:
        formatter_selection = [x.strip() for x in selection.split("|") if x]
        key = formatter_selection[0].lower().replace(" ", "_")
        value = False if formatter_selection[1] == "True" else True
        result[key] = value
    return result


def base_checkbox_menu(data: List, menu_title: str) -> List:
    selection = questionary.checkbox(menu_title, choices=data, qmark=use_emoji_maybe("\u2699\ufe0f")).ask()
    if selection in [None, []]:
        flush_lines(4)
        return selection
    flush_lines(1)
    return selection
