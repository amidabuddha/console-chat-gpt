from typing import Dict, Union

import toml

from console_gpt.config_manager import (CONFIG_PATH, CONFIG_SAMPLE_PATH,
                                        _load_toml, fetch_variable)
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import use_emoji_maybe
from console_gpt.menus.skeleton_menus import (base_multiselect_menu,
                                              preview_multiselect_menu)
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
    default_assistant = fetch_variable("managed", "assistant")
    all_models = fetch_variable("models")

    if default_model not in all_models:
        default_model = list(all_models.keys())[0]
        _show_menu = True

    if not _show_menu:
        model_data = all_models[default_model]
        model_data.update(dict(model_title=default_model))
        return model_data

    # Add new options for model management
    menu_data = list(all_models.keys())
    menu_data.extend(["ollama", "Add model(s)", "Remove model(s)", "Change default model"])
    menu_title = "{} Select a model:".format(use_emoji_maybe("\U0001f916"))
    selection = base_multiselect_menu("Model menu", menu_data, menu_title, default_model)

    if selection == "Add model(s)":
        # Load models from config.toml.sample
        sample_data = _load_toml(CONFIG_SAMPLE_PATH)
        sample_models = sample_data["chat"]["models"]
        current_models = all_models.keys()
        add_candidates = [k for k in sample_models.keys() if k not in current_models]
        if not add_candidates:
            custom_print("info", "No new models available to add from config.toml.sample.")
            return model_menu()
        # Show preview menu for adding models
        menu_items = [{"label": k, "preview": str(sample_models[k])} for k in add_candidates]
        selected = preview_multiselect_menu(menu_items, "Add model(s)", preview_title="Model details", select=False)
        if selected:
            config = _load_toml(CONFIG_PATH)
            for k in selected:
                config["chat"]["models"][k] = sample_models[k]
            with open(CONFIG_PATH, "w") as f:
                toml.dump(config, f)
            custom_print("ok", f"Added model(s): {', '.join(selected)}")
        return model_menu()

    if selection == "Remove model(s)":
        # List current models for removal
        current_models = list(all_models.keys())
        if not current_models:
            custom_print("info", "No models available to remove.")
            return model_menu()
        # Fetch defaults
        menu_items = [{"label": k, "preview": str(all_models[k])} for k in current_models]
        selected = preview_multiselect_menu(menu_items, "Remove model(s)", preview_title="Model details")
        to_remove = set(selected or [])
        # Check for protected models
        protected_model = default_model if default_model in to_remove else None
        protected_assistant = default_assistant if default_assistant in to_remove else None
        if protected_model:
            custom_print("warn", f"Cannot remove model set as default model: {protected_model}. It will be kept.")
            to_remove.discard(protected_model)
        if protected_assistant:
            custom_print(
                "warn", f"Cannot remove model set as default assistant: {protected_assistant}. It will be kept."
            )
            to_remove.discard(protected_assistant)
        if to_remove:
            config = _load_toml(CONFIG_PATH)
            for k in to_remove:
                config["chat"]["models"].pop(k, None)
            with open(CONFIG_PATH, "w") as f:
                toml.dump(config, f)
            custom_print("ok", f"Removed model(s): {', '.join(to_remove)}")
        return model_menu()

    if selection == "Change default model":
        # Allow user to select a new default model from current models
        current_models = list(all_models.keys())
        if not current_models:
            custom_print("info", "No models available to set as default.")
            return model_menu()
        menu_title = "{} Select a new default model:".format(use_emoji_maybe("\U0001f916"))
        new_default = base_multiselect_menu(
            "Change default model", current_models, menu_title, default_model, exit=False
        )
        if new_default and new_default in current_models:
            config = _load_toml(CONFIG_PATH)
            config["chat"]["defaults"]["model"] = new_default
            with open(CONFIG_PATH, "w") as f:
                toml.dump(config, f)
            custom_print("ok", f"Default model changed to: {new_default}")
        return model_menu()

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
            return model_menu()
    else:
        model_data = all_models[selection]
    model_data.update(dict(model_title=selection))
    return model_data
