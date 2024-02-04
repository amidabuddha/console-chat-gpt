import glob
import json
import os
import shutil
import textwrap
from typing import List, Optional, Tuple

import openai
import requests

from console_gpt.config_manager import ASSISTANTS_PATH, fetch_variable, write_to_config
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import capitalize, decapitalize
from console_gpt.menus.role_menu import _add_custom_role, role_menu
from console_gpt.menus.skeleton_menus import (
    base_checkbox_menu,
    base_multiselect_menu,
    base_settings_menu,
)
from console_gpt.prompts.file_prompt import _validate_file, browser_files
from console_gpt.prompts.save_chat_prompt import _validate_confirmation
from console_gpt.prompts.system_prompt import system_reply

"""
Assistant Selection Menu
"""
OPENAI_URL = "https://api.openai.com"
ASSISTANTS_ENDPOINT = "/v1/assistants"
FILES_ENDPOINT = "/v1/files"


def assistant_menu(model) -> Optional[Tuple]:
    """
    If assitant mode is enabled collect the necessary data to create a new one.
    :return: assitant enablement state (boolean) for the current chat session, optionally tools to be used
    """
    assistant_entity = None
    if fetch_variable("features", "assistant_mode"):
        conversation_selection = base_multiselect_menu(
            "Conversation menu",
            ["Assistant", "Chat"],
            "Please select the converstaion type",
            "Assistant",
            preview_command=_conversation_preview,
        )
        if conversation_selection == "Assistant":
            my_assistants = _list_assistants(model)
            if not my_assistants:
                role_title = _new_assistant(model)
                assistant_id, thread_id = _get_local_assistant(role_title)
                assistant_entity = role_title, assistant_id, thread_id
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


def _assistant_init(model, assistant_tools, assistant_files, role_title, role) -> Tuple:
    # Step 1: Initialize  an Assistant
    client = openai.OpenAI(api_key=model["api_key"])
    tools = [] if assistant_tools == None else assistant_tools
    files = [] if assistant_files == None else assistant_files
    assistant = client.beta.assistants.create(
        name=role_title, instructions=role, tools=tools, file_ids=files, model=model["model_name"]
    )
    # Step 2: Create a Thread
    thread_id = _create_thread(model)
    if assistant and thread_id:
        _save_assistant(model, role_title, assistant.id, thread_id)
    return role_title, assistant.id, thread_id


def _list_assistants(model) -> Optional[List[str]]:
    api_key = model["api_key"]
    # Get assistants stored locally
    local_assistants_names = [
        os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, "*.json"))
    ]
    # Get assistants stored on OpenAI servers
    params = {
        "order": "desc",
        "limit": "20",
    }
    list_assistants = requests.get(
        f"{OPENAI_URL}{ASSISTANTS_ENDPOINT}",
        params=params,
        headers={"OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {api_key}"},
    ).json()
    remote_assistants = [
        {"assistant_id": assistant["id"], "role_title": decapitalize(assistant["name"])}
        for assistant in list_assistants["data"]
    ]
    remote_assistants_roles = {d["role_title"] for d in remote_assistants}
    # Remove local assistants that do not exist online
    local_only = [role for role in local_assistants_names if role not in remote_assistants_roles]
    if local_only:
        for assistant in local_only:
            assistant_path = os.path.join(ASSISTANTS_PATH, assistant + ".json")
            os.remove(assistant_path)
            custom_print("info", f'Local Assistant "{capitalize(assistant)}" does not exist online, removed.')
    # Remove existing assistants from the fetched list of remote assistants
    filtered_remote_assistants = [
        role for role in remote_assistants if role["role_title"] not in local_assistants_names
    ]
    for assistant in filtered_remote_assistants:
        _save_assistant(model, assistant["role_title"], assistant["assistant_id"])
    updated_local_assistants_names = [
        os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, "*.json"))
    ]
    return updated_local_assistants_names


def _new_assistant(model):
    role_title, role = role_menu()
    assistant_tools = _select_assistant_tools()
    assistant_files = _selected_remote_files(model)
    # Check if this assistant already exist
    if os.path.exists(os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")):
        overwrite = custom_input(
            message="This assistant already exist, would you like to overwrite? (Y/N):",
            validate=_validate_confirmation,
        )
        if overwrite in ["n", "no"]:
            return _new_assistant(model)
        else:
            _modify_assisstant(model, role_title, role, assistant_tools, assistant_files)
    else:
        _assistant_init(model, assistant_tools, assistant_files, role_title, role)
    return role_title


def _selected_remote_files(model):
    upload_files = custom_input(
        message="Would you like to upload any files to be used by the Assistant? (Y/N):",
        validate=_validate_confirmation,
    )
    if upload_files in ["y", "yes"]:
        files = _upload_files(model)
        return files
    else:
        return None


def _upload_files(model):
    files = []
    while True:
        added_file = _upload_file(model)
        if added_file:
            files.append(added_file)
        more_files = custom_input(
            message="Would you like to upload another file? (Y/N):",
            validate=_validate_confirmation,
        )
        if more_files in ["y", "yes"]:
            continue
        else:
            return files


def _select_assistant_tools():
    tools_selection = base_settings_menu(
        {
            "code_interpreter": "Allows the Assistants API to write and run Python code",
            "retrieval": "Augments the Assistant with knowledge from outside its model",
        },
        " Assistant tools",
    )
    match tools_selection:
        case {"code_interpreter": True, "retrieval": True}:
            system_reply("Code interpreter and Retrieval tools added to this Assistant.")
            return [{"type": "code_interpreter"}, {"type": "retrieval"}]
        case {"code_interpreter": True}:
            system_reply("Code interpeter tool added to this Assistant.")
            return [{"type": "code_interpreter"}]
        case {"retrieval": True}:
            system_reply("Retrieval tool added to this Assistant.")
            return [{"type": "retrieval"}]
        case _:
            system_reply("No tools selected.")
            return None


def _get_local_assistant(name):
    assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(name) + ".json")
    with open(assistant_path, "r") as file:
        data = json.load(file)
        assistant_id = data["assistant_id"]
        thread_id = data["thread_id"]
    return assistant_id, thread_id


def _get_remote_assistant(model, id):
    api_key = model["api_key"]
    url = f"{OPENAI_URL}{ASSISTANTS_ENDPOINT}/{id}"
    headers = {"Content-Type": "application/json", "OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {api_key}"}
    assistant = requests.get(url.format(id=id), headers=headers).json()
    if assistant["id"] == id:
        return assistant
    else:
        custom_print("error", "Something went wrong, assistant was not retrieved...")
        return _get_remote_assistant(model, id)


def _modify_assisstant(model, name, instructions, tools, files):
    new_tools = [] if tools == None else tools
    new_files = [] if files == None else files
    id, _ = _get_local_assistant(name)
    old_files = _get_remote_assistant(model, id)["file_ids"]
    if new_files != old_files:
        _delete_assistant_files(model, id)
    api_key = model["api_key"]
    url = f"{OPENAI_URL}{ASSISTANTS_ENDPOINT}/{id}"
    headers = {"Content-Type": "application/json", "OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {api_key}"}
    data = {
        "instructions": instructions,
        "name": name,
        "tools": new_tools,
        "model": model["model_name"],
        "file_ids": new_files,
    }
    updated_assistant = requests.post(url.format(id=id), headers=headers, data=json.dumps(data)).json()
    if updated_assistant["tools"] == new_tools and updated_assistant["instructions"] == instructions:
        custom_print("info", f"Assistant {name} was succesfully updated!")
    else:
        custom_print("error", "Something went wrong, assistant was not updated...")
        return _modify_assisstant(model, name, instructions, tools, files)


def _delete_assistant_files(model, id):
    assistant_files = _get_remote_assistant(model, id)["file_ids"]
    for file in assistant_files:
        _delete_file(model, file)


def _delete_assistant(model, assistants):
    client = openai.OpenAI(api_key=model["api_key"])
    removed_assistants = base_checkbox_menu(assistants, " Assistant removal:")
    for assistant in removed_assistants:
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(assistant) + ".json")
        with open(assistant_path, "r") as file:
            data = json.load(file)
        assistant_id = data["assistant_id"]
        thread_id = data["thread_id"]
        _delete_assistant_files(model, assistant_id)
        response = client.beta.assistants.delete(assistant_id)
        print(response)
        try:
            response = client.beta.threads.delete(thread_id)
            print(response)
        except openai.NotFoundError as e:
            print(e)
        os.remove(assistant_path)
        custom_print("info", f"Assistant {assistant_path}  successfully deleted.")


def _create_thread(model) -> str:
    api_key = model["api_key"]
    client = openai.OpenAI(api_key=api_key)
    thread = client.beta.threads.create()
    return thread.id


def _save_assistant(model, role_title, assistant_id, thread_id=None):
    if not thread_id:
        custom_print("info", f'Remote assistant "{capitalize(role_title)}" will be saved locally!')
        thread_provided = custom_input(
            message="Enter an existing thread ID or press Enter to create a new one:",
        )
        if thread_provided != "":
            thread_id = thread_provided
        else:
            thread_id = _create_thread(model)
    assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")
    with open(assistant_path, "w", encoding="utf-8") as file:
        json.dump({"assistant_id": assistant_id, "thread_id": thread_id}, file, indent=4, ensure_ascii=False)
    set_default = custom_input(
        message="Would you like to set this Assistant as default? (Y/N):",
        validate=_validate_confirmation,
    )
    if set_default in ["y", "yes"]:
        write_to_config("defaults", "system_role", new_value=decapitalize(role_title))


def _assistant_selection_menu(model):
    assistants_names = [
        os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, "*.json"))
    ]
    selection_menu = [capitalize(name) for name in assistants_names]
    selection_menu.append("Create New Assistant")
    if assistants_names:
        selection_menu.append("Edit an Assistant")
        selection_menu.append("Delete an Assistant")
    config_default_role = fetch_variable("defaults", "system_role")
    if config_default_role in assistants_names:
        default_role = capitalize(config_default_role)
    else:
        default_role = "Create New Assistant"
    assistant_selection = base_multiselect_menu(
        "Assistant menu",
        selection_menu,
        "Please select your Assistant:",
        default_role,
        preview_command=_assistant_preview,
    )
    match assistant_selection:
        case "Create New Assistant":
            _new_assistant(model)
            return _assistant_selection_menu(model)
        case "Edit an Assistant":
            _edit_assistant_menu(model, assistants_names)
            return _assistant_selection_menu(model)
        case "Delete an Assistant":
            _delete_assistant(model, assistants_names)
            return _assistant_selection_menu(model)
    assistant_id, thread_id = _get_local_assistant(assistant_selection)
    return assistant_selection, assistant_id, thread_id


def _edit_assistant_menu(model, assistants):
    assistant_selection_menu = [capitalize(name) for name in assistants]
    edited_assistant = base_multiselect_menu(
        "Edit assistant menu",
        assistant_selection_menu,
        "Please select an Assistant to edit:",
        exit=False,
    )
    _edit_tools(model, edited_assistant)


def _edit_tools(model, assistant):
    id, _ = _get_local_assistant(assistant)
    remote_assistant = _get_remote_assistant(model, id)
    edit_menu = ["Done editing", "Edit Assistant tools", "Update Assistant instructions", "Add/remove Assistant files"]
    edit_menu_selection = base_multiselect_menu(
        "Assistant settings",
        edit_menu,
        "Select a setting to edit:",
        exit=False,
    )
    match edit_menu_selection:
        case "Done editing":
            return
        case "Edit Assistant tools":
            new_assistant_tools = _select_assistant_tools()
            _modify_assisstant(
                model,
                remote_assistant["name"],
                remote_assistant["instructions"],
                new_assistant_tools,
                remote_assistant["file_ids"],
            )
            return _edit_tools(model, assistant)
        case "Update Assistant instructions":
            new_assistant_instructions = _add_custom_role(assistant, True)
            _modify_assisstant(
                model,
                remote_assistant["name"],
                new_assistant_instructions,
                remote_assistant["tools"],
                remote_assistant["file_ids"],
            )
            return _edit_tools(model, assistant)
        case "Add/remove Assistant files":
            _assistant_files_menu(model, remote_assistant)
            return _edit_tools(model, assistant)


def _assistant_files_menu(model, assistant):
    upload_file_str = f'Upload a file to "{assistant["name"]}"'
    remove_files_str = f'Remove files from "{assistant["name"]}"'
    files = assistant["file_ids"]
    selection_menu = [upload_file_str]
    if files:
        selection_menu.append(remove_files_str)
    files_menu_selection = base_multiselect_menu(
        "Add/remove Assistant files",
        selection_menu,
        "Add/remove Assistant files",
        exit=False,
    )
    if files_menu_selection == upload_file_str:
        _create_assistant_file(model, assistant)
    elif files_menu_selection == remove_files_str:
        _remove_assistant_files(model, assistant)


def _upload_file(model):
    api_key = model["api_key"]
    file_path = browser_files("Select a file:", "File selection cancelled.", _validate_file)
    if not file_path:
        return None
    url = f"{OPENAI_URL}{FILES_ENDPOINT}"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "purpose": "assistants",
    }
    files = {
        "file": open(file_path, "rb"),
    }
    file_upload = requests.post(url, headers=headers, data=data, files=files)
    files["file"].close()
    if file_upload.status_code == 200:
        file_id = file_upload.json()["id"]
        file_name = file_upload.json()["filename"]
        custom_print("info", f'File "{file_name}" uploaded successfully.')
        return file_id
    else:
        custom_print("error", "Failed to upload the file.")
        print(f"Error: {file_upload.text}")
        return None


def _create_assistant_file(model, assistant):
    api_key = model["api_key"]
    file = _upload_file(model)
    if file:
        assistant_id = assistant["id"]
        url = f"{OPENAI_URL}{ASSISTANTS_ENDPOINT}/{assistant_id}/files"
        headers = {
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v1",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "file_id": file,
        }
        assistant_file = requests.post(
            url.format(assistant_id=assistant_id), headers=headers, data=json.dumps(data)
        ).json()
        if file == assistant_file["id"]:
            custom_print("info", f'Assistant "{assistant["name"]}" was succesfully updated!')
        else:
            custom_print("error", "Something went wrong, assistant was not updated...")
            return _create_assistant_file(model, assistant)


def _remove_assistant_files(model, assistant):
    api_key = model["api_key"]
    assistant_id = assistant["id"]
    assistant_name = assistant["name"]
    assistant_headers = {
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1",
        "Authorization": f"Bearer {api_key}",
    }
    assistant_files = assistant["file_ids"]
    url = f"{OPENAI_URL}{FILES_ENDPOINT}"
    headers = {"Authorization": f"Bearer {api_key}"}
    remote_files = requests.get(url, headers=headers).json()
    remote_assistant_files = [
        {"id": file_data["id"], "filename": file_data["filename"]}
        for file_data in remote_files["data"]
        if file_data["id"] in assistant_files
    ]
    filenames_to_remove = base_checkbox_menu(
        [file["filename"] for file in remote_assistant_files], "Select files to remove:"
    )
    files_to_remove = [item["id"] for item in remote_assistant_files if item["filename"] in filenames_to_remove]
    for fileid in files_to_remove:
        assistant_fileurl = f"{OPENAI_URL}{ASSISTANTS_ENDPOINT}/{assistant_id}/files/{fileid}"
        response = requests.delete(assistant_fileurl, headers=assistant_headers).json()
        if response["deleted"] == True:
            custom_print(
                "info",
                f'File "{next(item["filename"] for item in remote_assistant_files if item["id"]==fileid)}"" successfully removed from {assistant_name}.',
            )
        confirmation = _delete_file(model, fileid)
        if confirmation == True:
            custom_print(
                "info",
                f'File "{next(item["filename"] for item in remote_assistant_files if item["id"]==fileid)}" deleted successfully.',
            )


def _delete_file(model, id):
    api_key = model["api_key"]
    url = f"{OPENAI_URL}{FILES_ENDPOINT}/{id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.delete(url, headers=headers).json()
    return response["deleted"]


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
        case "Edit an Assistant":
            return "Change settings of any existing assistant."
        case "Delete an Assistant":
            return "Remove one or more existing assistants."
        case "Exit":
            return "Terminate the application."
        case _:
            return "\n".join(textwrap.wrap(all_roles.get(decapitalize(item), "Unknown Option"), width=line_length))
