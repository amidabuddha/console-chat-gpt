from typing import Dict, Union

from console_gpt.config_manager import fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import use_emoji_maybe
from console_gpt.menus.skeleton_menus import base_multiselect_menu
from console_gpt.ollama_helper import get_ollama

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
    menu_data.append("ollama")
    menu_title = "{} Select a model:".format(use_emoji_maybe("\U0001f916"))
    selection = base_multiselect_menu("Model menu", menu_data, menu_title, default_model)
    if selection == "ollama":
        models = get_ollama()
        if models:
            menu_title = "{} Select a locally hosted model:".format(use_emoji_maybe("\U0001f916"))
            local_selection = base_multiselect_menu("Ollama models", models, menu_title)
            model_data = {
                "api_key": "ollama",
                "base_url": "http://localhost:11434/v1",
                "model_input_pricing_per_1k": 0,
                "model_max_tokens": 0,
                "model_name": local_selection,
                "model_output_pricing_per_1k": 0,
                "reasoning_effort": False,
            }
        else:
            custom_print("info", "No models found in Ollama. Please check the Ollama server or select another model.")
            model_menu()
    else:
        model_data = all_models[selection]
    model_data.update(dict(model_title=selection))
    return model_data
