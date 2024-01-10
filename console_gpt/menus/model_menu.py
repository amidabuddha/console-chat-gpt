import json
import os
import shutil
from typing import Dict, List, Optional, Tuple, Union

import openai

from console_gpt.config_manager import ASSISTANTS_PATH, fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import decapitalize, use_emoji_maybe
from console_gpt.menus.role_menu import role_menu
from console_gpt.menus.skeleton_menus import base_multiselect_menu, base_settings_menu
from console_gpt.prompts.system_prompt import system_reply

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
        assistant_selection = base_multiselect_menu("Conversation menu",["Assistant", "Chat"], "Please select the converstaion type", "Assistant",preview_command=_conversation_preview)
        if assistant_selection == "Assistant":
            #TODO select existing assistant + option to delete assistants
            role_title, role = role_menu()
            tools_selection = base_settings_menu({"code_interpreter":"Allows the Assistants API to write and run Python code","retrieval":"Augments the Assistant with knowledge from outside its model"}, " Assistant tools")
            match tools_selection:
                case {'code_interpreter': True, 'retrieval': True}:
                    system_reply("Code interpreter and Retrieval tools added to this Assistant.")
                    assistant_tools = [{"type": "code_interpreter"},{"type": "retrieval"}]
                case {'code_interpreter': True}:
                    system_reply("Code interpeter tool added to this Assistant.")
                    assistant_tools = [{"type": "code_interpreter"}]
                case {'retrieval': True}:
                    system_reply("Retrieval tool added to this Assistant.")
                    assistant_tools = [{"type": "retrieval"}]
                case _:
                    system_reply("No tools selected.")
                    assistant_tools = None
            assistant_entity = assistant_init(model, assistant_tools, role_title, role)
    return assistant_entity

def _conversation_preview(item: str) -> str:
    """
    Returns a short description of the hovered conversation type inside the menu
    :param item: The conversation type.
    :return: The preview of the conversation.
    """
    match item:
        case "Assistant":
            return "Unlimited multi-turn conversations."
        case "Chat":
            return "For single-turn or limited multi-turn conversations."
        case "Exit":
            return "Terminate the application."
        case _:
            return "Unknown Option"

def assistant_init(model, assistant_tools, role_title, role) -> Tuple:
    # Step 1: Create an Assistant
    client = openai.OpenAI(api_key=model["api_key"])
    tools = [] if assistant_tools == None else assistant_tools
    # TODO upload files for retrieval on assistant level: https://platform.openai.com/docs/assistants/tools/uploading-files-for-retrieval
    assistant = client.beta.assistants.create(
        name=role_title,
        instructions=role,
        tools=tools,
        model=model["model_name"]
    )
    # Step 2: Create a Thread
    thread = client.beta.threads.create()
    if assistant and thread:
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")
        with open(assistant_path, "w", encoding="utf-8") as file:
            json.dump({"assistant_id": assistant.id, "thread_id":thread.id}, file, indent=4, ensure_ascii=False)
        custom_print("info", f"Assistant successfully created and saved to - {assistant_path}")
    return [assistant.id, thread.id, tools]
