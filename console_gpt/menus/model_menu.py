from typing import Dict, Union

from console_gpt.config_manager import ASSISTANTS_PATH, fetch_variable
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
    all_models = fetch_variable("models")

    if default_model not in all_models:
        default_model = list(all_models.keys())[0]
        _show_menu = True

    if not _show_menu:
        model_data = all_models[default_model]
        model_data.update(dict(model_title=default_model))
        return model_data

    # Build the menu based on the available models (chat.models.<model>)
    menu_data = list(all_models.keys())
    menu_title = "{} Select a model:".format(use_emoji_maybe("\U0001F916"))
    selection = base_multiselect_menu("Model menu", menu_data, menu_title, default_model)
    model_data = all_models[selection]
    model_data.update(dict(model_title=selection))
    return model_data
