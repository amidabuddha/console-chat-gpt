from console_gpt.config_manager import write_to_config
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print


def set_api_key(model):
    my_key = custom_input(message=f'Your API key for model "{model["model_title"]}" is not set, please enter:')
    if len(my_key) > 30:
        write_to_config("models", model["model_title"], "api_key", new_value=my_key)
        custom_print("info", f'API key "{my_key}" succesfully added to model "{model["model_title"]}"')
        model["api_key"] = my_key
        return model
    else:
        custom_print("error", "Invalid key, please try again")
        return set_api_key(model)
