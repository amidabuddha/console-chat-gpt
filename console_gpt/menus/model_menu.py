import json
import os
from typing import Dict, List, Optional, Tuple, Union

import openai

from console_gpt.config_manager import ASSISTANTS_PATH, fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import decapitalize, use_emoji_maybe
from console_gpt.menus.role_menu import role_menu
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

def assistant_menu(model) -> Optional[Tuple]:
    """
    If assitant mode is enabled collect the necessary data to create a new one.
    :return: assitant enablement state (boolean) for the current chat session, optionally tools to be used
    """
    assistant_entity = None
    if fetch_variable("features", "assistant_mode"):
        assistant_selection = base_multiselect_menu("Assistant menu",["yes", "no"], "Would you like to try the beta assistant mode by OpenAI?", "no")
        if assistant_selection == "yes":
            #TODO select existing assistant + option to delete assistants
            role_title, role = role_menu()
            tools_selection = base_multiselect_menu("Assistant tools menu",["Code interpreter tool","Retrieval tool", "Both Code interpreter and Retrieval tools"], "Should we enable any of the following tools on the assistant?:", 0, True)
            match tools_selection:
                case "Code interpreter tool":
                    tools = [{"type": "code_interpreter"}]
                case "Retrieval tool":
                    tools = [{"type": "retrieval"}]
                case "Both Code interpreter and Retrieval tools":
                    tools = [{"type": "code_interpreter"},{"type": "retrieval"}]
                case _:
                    tools = None
            assistant_entity = assistant_init(model, tools, role_title, role)
    return assistant_entity

def assistant_init(model, tools, role_title, role) -> Tuple:
    # Step 1: Create an Assistant
    client = openai.OpenAI(api_key=model["api_key"])
    new_tools = [] if tools == None else tools
    # TODO upload files for retrieval on assistant level: https://platform.openai.com/docs/assistants/tools/uploading-files-for-retrieval
    assistant = client.beta.assistants.create(
        name=role_title,
        instructions=role,
        tools=new_tools,
        model=model["model_name"]
    )
    # Step 2: Create a Thread
    thread = client.beta.threads.create()
    if assistant and thread:
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")
        with open(assistant_path, "w", encoding="utf-8") as file:
            json.dump({"assistant_id": assistant.id, "thread_id":thread.id, "last_message":""}, file, indent=4, ensure_ascii=False)
        custom_print("info", f"Assistant successfully created and saved to - {assistant_path}")
    return [assistant.id, thread.id, "", new_tools]
