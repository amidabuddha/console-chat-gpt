import re
import shutil
import textwrap
from typing import Optional, Tuple, Union

from questionary import Style

from console_gpt.catch_errors import eof_wrapper
from console_gpt.config_manager import fetch_variable, write_to_config
from console_gpt.custom_stdin import custom_input
from console_gpt.general_utils import capitalize, decapitalize, use_emoji_maybe
from console_gpt.menus.skeleton_menus import base_checkbox_menu, base_multiselect_menu


def _role_preview(item: str) -> str:
    """
    Returns a preview of the hovered role inside the menu
    :param item: The role name.
    :return: The preview of the role.
    """
    default_role = fetch_variable("defaults", "system_role")
    all_roles = fetch_variable("roles")
    # Check the size of the terminal
    line_length = int(shutil.get_terminal_size().columns)
    match item:
        case "Add New System Behavior":
            return "Provide detailed instructions of the desired GPT behavior."
        case "Remove System Behavior":
            return "Remove an existing behavior."
        case "Exit":
            return "Terminate the application."
        case "Default":
            return "\n".join(
                textwrap.wrap(
                    all_roles.get(default_role, "Unknown"),
                    width=line_length,
                )
            )
        case _:
            return "\n".join(textwrap.wrap(all_roles.get(decapitalize(item), "Unknown Option"), width=line_length))


def _validate_title(val: str) -> Union[str, bool]:
    """
    Sub-function to _add_custom_role() which validates
    the user input and does not allow empty values or
    giving title which already exists
    :param val: The STDIN from the user
    :return: Either error string or bool to confirm that
    the user input is valid
    """
    all_roles_names = list(fetch_variable("roles").keys())
    if not val or val.startswith(" "):
        return "Empty input not allowed!"
    if val in all_roles_names:
        return "Role already exists!"
    return True


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


def _remove_custom_role() -> None:
    """
    Sub-function to role_menu() which allows removing existing roles
    :return: Nothing, just write to the config.
    """
    roles_data = fetch_variable("roles")
    roles_names = roles_data.keys()
    removed_roles = base_checkbox_menu(roles_names, " Role removal:")
    if removed_roles is not None:
        # Removes the items from the Dict
        [roles_data.pop(x, None) for x in removed_roles]
        write_to_config("roles", new_value=roles_data)


@eof_wrapper
def _add_custom_role() -> None:
    """
    Sub-function to role_menu() which allows adding new roles
    :return: Nothing, just write to the config.
    """
    style = Style(
        [
            ("qmark", "fg:#86cdfc bold"),
            ("question", "fg:#ffdb38 bold"),
            ("answer", "fg:#69faff bold"),
        ]
    )
    title = custom_input(message="Enter a title for the new role:", style=style, qmark="❯", validate=_validate_title)
    # Catch empty spaces, tabs or new lines. Otherwise, will break the config
    title = re.sub(r"(\t|\s|\n)+", "_", title)
    description = custom_input(
        is_single_line=False,
        message="Enter description:",
        style=style,
        qmark="❯",
        validate=_validate_description,
        multiline=True,
    )
    write_to_config("roles", title, new_value=description)


def role_menu() -> Tuple[Optional[str],Optional[str]]:
    """
    Generates a menu with all available roles in the config
    :return: The role description or exists with message on "Exit" or SIGINT
    """
    # Checks if the menu should be displayed at all
    _show_menu = fetch_variable("features", "role_selector")
    # Fetch default role
    default_role = capitalize(fetch_variable("defaults", "system_role"))

    if not _show_menu:
        return capitalize(fetch_variable("roles", default_role))

    # Generate a list based on the role title (chat.roles.<role>)
    role_titles = list(fetch_variable("roles").keys())
    role_titles = [capitalize(title) for title in role_titles] 

    # Add option to Add new roles
    role_titles.append("Add New System Behavior")

    # Add option to remove roles
    role_titles.append("Remove System Behavior")

    menu_title = "{} Select a role:".format(use_emoji_maybe("\U0001F3AD"))
    selection = base_multiselect_menu(
        "Role Menu", role_titles, menu_title, default_value=default_role, preview_command=_role_preview
    )
    match selection:
        case "Add New System Behavior":
            _add_custom_role()
            return role_menu()
        case "Remove System Behavior":
            _remove_custom_role()
            return role_menu()
    return selection, fetch_variable("roles", decapitalize(selection))