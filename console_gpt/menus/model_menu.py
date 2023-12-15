from typing import Dict, Union

from console_gpt.config_manager import fetch_variable
from console_gpt.general_utils import use_emoji_maybe
from console_gpt.menus.skeleton_menus import base_multiselect_menu

"""
Model Selection Menu
"""


def model_menu() -> Dict[str, Union[int, str, float]]:
    """
    Generates a menu for all available GPT models in the config
    The format of the menu is scrollable with a single select
    :return: Dictionary with the model data
    """
    # Checks whether the menu should be shown
    _show_menu = fetch_variable("features", "model_selector")

    # Fetches the default model
    default_model = fetch_variable("defaults", "model")
    if not _show_menu:
        return fetch_variable("models", default_model)

    # Build the menu based on the available models (chat.models.<model>)
    menu_data = list(fetch_variable("models").keys())
    menu_title = "{} Select a model:".format(use_emoji_maybe("\U0001F916"))
    selection = base_multiselect_menu(menu_data, menu_title, default_model)
    return fetch_variable("models", selection)
