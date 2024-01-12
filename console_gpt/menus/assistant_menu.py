import glob
import json
import os
import shutil
import textwrap
from typing import Any, Dict, List, Optional, Tuple, Union

import openai
import requests

from console_gpt.config_manager import ASSISTANTS_PATH, fetch_variable, write_to_config
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import capitalize, decapitalize
from console_gpt.menus.role_menu import role_menu
from console_gpt.menus.skeleton_menus import (
    base_checkbox_menu,
    base_multiselect_menu,
    base_settings_menu,
)
from console_gpt.prompts.save_chat_prompt import _validate_confirmation
from console_gpt.prompts.system_prompt import system_reply

"""
Assistant Selection Menu
"""

def assistant_menu(model) -> Optional[Tuple]:
    """
    If assitant mode is enabled collect the necessary data to create a new one.
    :return: assitant enablement state (boolean) for the current chat session, optionally tools to be used
    """
    assistant_entity = None
    if fetch_variable("features", "assistant_mode"):
        conversation_selection = base_multiselect_menu("Conversation menu",["Assistant", "Chat"], "Please select the converstaion type", "Assistant",preview_command=_conversation_preview)
        if conversation_selection == "Assistant":
            my_assistants = _list_assistants(model)
            if not my_assistants:
                role_title, role, assistant_tools = _new_assistant()
                assistant_entity = _assistant_init(model, assistant_tools, role_title, role)
            else:
                assistant_entity = _assistant_selection_menu(model)
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

def _assistant_init(model, assistant_tools, role_title, role) -> Tuple:
    # Step 1: Initialize  an Assistant
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
    thread_id = _create_thread(model)
    if assistant and thread_id:
        _save_assistant(model, role_title,assistant.id,thread_id)
    return role_title, assistant.id, thread_id

def _list_assistants(model) -> None|Optional[List[str]]:
    api_key=model["api_key"]
    # Get assistants stored locally
    local_assistants_names = [os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, '*.json'))]
    # Get assistants stored on OpenAI servers
    list_assistants = requests.get("https://api.openai.com/v1//assistants?order=desc".format(limit=20), headers={"OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {api_key}"}).json()
    remote_assistants = [
        {"assistant_id":assistant["id"],"role_title":decapitalize(assistant["name"])}
        for assistant in list_assistants["data"]
        ]
    # Remove existing assistants from the fetched list of remote assistants
    filtered_remote_assistants = [role for role in remote_assistants if role["role_title"] not in local_assistants_names]       
    for assistant in filtered_remote_assistants:
        _save_assistant(model, assistant["role_title"], assistant["assistant_id"])   
    updated_local_assistants_names = [os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, '*.json'))]                                              
    return updated_local_assistants_names

def _new_assistant():
    role_title, role = role_menu()
    # Check if this assistant already exist
    if os.path.exists(os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + '.json')):
        overwrite = custom_input(message="This assistant already exist, would you like to overwrite? (Y/N):",
                validate=_validate_confirmation,
            )
        if overwrite in ["n", "no"]:
            return _new_assistant()
        else:
            role_title = "NEW " + role_title
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
    return (role_title, role, assistant_tools)

def _delete_assistant(model, assistants):
    client = openai.OpenAI(api_key=model["api_key"])
    removed_assistants = base_checkbox_menu(assistants, " Assistant removal:")
    for assistant in removed_assistants:
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(assistant) + ".json")
        with open(assistant_path, 'r') as file:                                                
            data = json.load(file)
        assistant_id = data["assistant_id"]
        thread_id = data["thread_id"]
        response = client.beta.assistants.delete(assistant_id)
        print(response)
        response = client.beta.threads.delete(thread_id)
        print(response)
        os.remove(assistant_path)
        custom_print("info", f"Assistant {assistant_path}  successfully deleted ")

def _create_thread(model) -> str:
    api_key=model["api_key"]
    client = openai.OpenAI(api_key=api_key)
    thread = client.beta.threads.create()
    return thread.id

def _save_assistant(model, role_title, assistant_id, thread_id=None):
        if not thread_id:
            custom_print("info", f'Remote assistant "{capitalize(role_title)}" will be saved locally!')
            thread_provided = (
                custom_input(
                message="Enter an existing thread ID or press Enter to create a new one:",
            ))
            if thread_provided != '':
                thread_id = thread_provided
            else:
                thread_id = _create_thread(model)  
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")
        with open(assistant_path, "w", encoding="utf-8") as file:
            json.dump({"assistant_id": assistant_id, "thread_id":thread_id}, file, indent=4, ensure_ascii=False)
        set_default = custom_input(message="Would you like to set this Assistant as default? (Y/N):",
                validate=_validate_confirmation,
            )
        if set_default in ["y", "yes"]:
            write_to_config("defaults", "system_role", new_value=decapitalize(role_title))

def _assistant_selection_menu(model):
    assistants_names = [os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, '*.json'))]
    selection_menu = [capitalize(name) for name in assistants_names]
    selection_menu.append("Create New Assistant")
    if assistants_names:
        selection_menu.append("Delete an Assistant")
    config_default_role = fetch_variable("defaults", "system_role")
    if config_default_role in assistants_names:
        default_role = capitalize(config_default_role)
    else:
        default_role = "Create New Assistant"
    assistant_selection = base_multiselect_menu("Assistant menu", selection_menu, "Please select yor Assistant:", default_role, preview_command=_assistant_preview)
    match assistant_selection:
        case "Create New Assistant":
            name, instructions, tools = _new_assistant()
            _assistant_init(model, tools, name, instructions)
            return _assistant_selection_menu(model)
        case "Delete an Assistant":
            _delete_assistant(model, assistants_names)
            return _assistant_selection_menu(model)
    assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(assistant_selection) + ".json")
    with open(assistant_path, 'r') as file:                                                
            data = json.load(file)
            assistant_id = data["assistant_id"]
            thread_id = data["thread_id"]
    return assistant_selection, assistant_id, thread_id

def _assistant_preview(item: str) -> str:
    """
    Returns a preview of the hovered assistant inside the menu
    :param item: The assistant name.
    :return: Instructions of the selected assistant.
    """
    all_roles = fetch_variable("roles")
    # Check the size of the terminal
    line_length = int(shutil.get_terminal_size().columns)
    match item:
        case "Create New Assistant":
            return "Setup your new assistant!"
        case "Delete an Assistant":
            return "Remove one or more existing assistants."
        case "Exit":
            return "Terminate the application."
        case _:
            return "\n".join(textwrap.wrap(all_roles.get(decapitalize(item), "Unknown Option"), width=line_length))
        
        