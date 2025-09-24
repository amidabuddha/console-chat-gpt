from pathlib import Path

import toml


def get_models():
    # Get the script's directory and construct path to config file
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "config.toml.sample"

    # Parse the TOML data
    data = toml.load(config_path)

    # Initialize the structures
    MODELS_LIST = {
        "anthropic_models": [],
        "mistral_models": [],
        "openai_models": [],
        "grok_models": [],
        "gemini_models": [],
    }

    MODELS_MAX_TOKEN = {}

    # Extract the models information
    models_data = data["chat"]["models"]

    # Populate the structures
    for model, model_data in models_data.items():
        model_name = model_data["model_name"]
        max_tokens = model_data["model_max_tokens"]

        # Fill MODELS_MAX_TOKEN
        MODELS_MAX_TOKEN[model_name] = int(max_tokens)

        # Fill MODELS_LIST
        if "anthropic" in model:
            MODELS_LIST["anthropic_models"].append(model_name)
        elif "tral" in model:
            MODELS_LIST["mistral_models"].append(model_name)
        elif any(sub in model for sub in ("gpt", "o3", "o4")):
            MODELS_LIST["openai_models"].append(model_name)
        elif "grok" in model:
            MODELS_LIST["grok_models"].append(model_name)
        elif "gemini" in model:
            MODELS_LIST["gemini_models"].append(model_name)

    return MODELS_LIST, MODELS_MAX_TOKEN
