from typing import Dict, List, Optional, Tuple, Union

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
        model_data = fetch_variable("models", default_model)
        model_data.update(dict(model_title=default_model))
        return model_data

    # Build the menu based on the available models (chat.models.<model>)
    menu_data = list(fetch_variable("models").keys())
    menu_title = "{} Select a model:".format(use_emoji_maybe("\U0001F916"))
    selection = base_multiselect_menu("Model menu", menu_data, menu_title, default_model)
    model_data = fetch_variable("models", selection)
    model_data.update(dict(model_title=selection))
    return model_data

def assistant_menu() -> Tuple[bool, Optional[List[Dict]]]:
    """
    If assitant mode is enabled collect the necessary data to create a new one.
    :return: assitant enablement state (boolean) for the current chat session, optionally tools to be used
    """
    assistant_entity = (False, None)
    if fetch_variable("features", "assistant_mode"):
        assistant_selection = base_multiselect_menu("Assistant menu",["yes", "no"], "Would you like to try the beta assistant mode by OpenAI?", "no")
        if assistant_selection == "yes":
            assistant_entity = (True, None)
            tools_selection = base_multiselect_menu("Assistant tools menu",["Code interpreter tool","Retrieval tool", "Both Code interpreter and Retrieval tools"], "Should we enable any of the following tools on the assistant?:", 0, True)
            match tools_selection:
                case "Code interpreter tool":
                    assistant_entity = (True, [{"type": "code_interpreter"}])
                case "Retrieval tool":
                    assistant_entity = (True, [{"type": "retrieval"}])
                case "Both Code interpreter and Retrieval tools":
                    assistant_entity = (True, [{"type": "code_interpreter"},{"type": "retrieval"}])
    return assistant_entity

