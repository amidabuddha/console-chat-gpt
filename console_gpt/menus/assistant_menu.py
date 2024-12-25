import glob
import json
import os
import shutil
import textwrap
import time
from typing import List, Optional, Tuple

from unichat.api_helper import openai

from console_gpt.config_manager import (ASSISTANTS_PATH, fetch_variable,
                                        write_to_config)
from console_gpt.custom_stdin import custom_input
from console_gpt.custom_stdout import custom_print, markdown_print
from console_gpt.general_utils import capitalize, decapitalize
from console_gpt.mcp_client import (MCPToolError, call_tool,
                                    get_available_tools, initialize_tools)
from console_gpt.menus.role_menu import _add_custom_role, role_menu
from console_gpt.menus.skeleton_menus import (base_checkbox_menu,
                                              base_multiselect_menu,
                                              base_settings_menu)
from console_gpt.menus.tools_menu import transform_tools_selection
from console_gpt.prompts.save_chat_prompt import _validate_confirmation
from console_gpt.prompts.system_prompt import system_reply

TIMEOUT = 300

# Internal Functions
## Menus


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


def _edit_assistant_menu(model, assistants):
    assistant_selection_menu = [capitalize(name) for name in assistants]
    edited_assistant = base_multiselect_menu(
        "Edit assistant menu",
        assistant_selection_menu,
        "Please select an Assistant to edit:",
        exit=False,
    )
    _edit_tools(model, edited_assistant)


## Assistant


def _new_assistant(model):
    role_title, role = role_menu()
    assistant_tools = _select_assistant_tools()
    # Check if this assistant already exist
    if os.path.exists(os.path.join(ASSISTANTS_PATH, decapitalize(role_title) + ".json")):
        overwrite = custom_input(
            message="This assistant already exist, would you like to overwrite? (Y/N):",
            validate=_validate_confirmation,
        )
        if overwrite in ["n", "no"]:
            return _new_assistant(model)
        else:
            _modify_assisstant(model, role_title, role, assistant_tools)
    else:
        _assistant_init(model, assistant_tools, role_title, role)
    return role_title


def _assistant_init(model, assistant_tools, role_title, role) -> Tuple:
    client = openai.OpenAI(api_key=model["api_key"])
    # Step 1: Initialize  an Assistant
    assistant = _create_assistant(client, model, assistant_tools, role_title, role)
    # Step 2: Create a Thread
    thread_id = _create_thread(model)
    if assistant and thread_id:
        _save_assistant(client, role_title, assistant.id, thread_id)
    return role_title, assistant.id, thread_id


def _get_local_assistant(name):
    assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(name) + ".json")
    with open(assistant_path, "r") as file:
        data = json.load(file)
        assistant_id = data["assistant_id"]
        thread_id = data["thread_id"]
    return assistant_id, thread_id


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


def _edit_tools(model, assistant):
    id, _ = _get_local_assistant(assistant)
    name, instructions, tools = _get_remote_assistant(model, id)
    edit_menu = ["Done editing", "Edit Assistant tools", "Update Assistant instructions"]
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
                name,
                instructions,
                new_assistant_tools,
            )
            return _edit_tools(model, assistant)
        case "Update Assistant instructions":
            new_assistant_instructions = _add_custom_role(assistant, True)
            _modify_assisstant(
                model,
                name,
                new_assistant_instructions,
                tools,
            )
            return _edit_tools(model, assistant)


# OpenAI Assistants
## Create assistant


def _select_assistant_tools():
    try:
        if fetch_variable("features", "mcp_client"):
            try:
                tools = get_available_tools()
            except MCPToolError:
                custom_print("warn", "MCP servers not initialized. Initializing...")
                tools = initialize_tools()
        else:
            tools = []
    except Exception as e:
        custom_print("error", f"Unexpected error: {str(e)}")
        tools = []
    menu_items = {"code_interpreter": "Allows the Assistants API to write and run Python code"}
    menu_items.update(
        {str(tool.get("name", "Unknown")): str(tool.get("description", "No description available")) for tool in tools}
    )
    tools_selection = base_settings_menu(menu_items, " Assistant tools")
    return transform_tools_selection(tools_selection, tools)


def _create_assistant(client, model, assistant_tools, role_title, role):
    tools = [] if assistant_tools == None else assistant_tools
    assistant = client.beta.assistants.create(
        instructions=role, name=role_title, tools=tools, model=model["model_name"]
    )
    return assistant


## List assistants


def _list_assistants(model) -> Optional[List[str]]:
    client = openai.OpenAI(api_key=model["api_key"])
    # Get assistants stored locally
    local_assistants_names = [
        os.path.splitext(os.path.basename(path))[0] for path in glob.glob(os.path.join(ASSISTANTS_PATH, "*.json"))
    ]
    # Get assistants stored on OpenAI servers
    list_assistants = client.beta.assistants.list(
        order="desc",
        limit="20",
    )
    remote_assistants = [
        {"assistant_id": assistant.id, "role_title": decapitalize(assistant.name)} for assistant in list_assistants
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


## Retrieve assistants


def _get_remote_assistant(model, id):
    client = openai.OpenAI(api_key=model["api_key"])
    assistant = client.beta.assistants.retrieve(id).model_dump_json()
    assistant_json = json.loads(assistant)
    if assistant_json["id"] == id:
        name = assistant_json["name"]
        instructions = assistant_json["instructions"]
        tools = assistant_json["tools"]
        return name, instructions, tools
    else:
        custom_print("error", "Something went wrong, assistant was not retrieved...")
        return _get_remote_assistant(model, id)


## Modify assistant


def _modify_assisstant(model, name, instructions, tools):
    client = openai.OpenAI(api_key=model["api_key"])
    new_tools = [] if tools == None else tools
    id, _ = _get_local_assistant(name)
    try:
        updated_assistant = client.beta.assistants.update(
            assistant_id=id, instructions=instructions, name=name, tools=new_tools, model=model["model_name"]
        ).model_dump_json()
    except openai.BadRequestError as e:
        custom_print("error", str(e))
        return
    updated_assistant_json = json.loads(updated_assistant)
    if updated_assistant_json["tools"] == new_tools and updated_assistant_json["instructions"] == instructions:
        custom_print("info", f"Assistant {name} was succesfully updated!")
    else:
        custom_print("error", "Something went wrong, assistant was not updated...")
        return _modify_assisstant(model, name, instructions, tools)


## Delete assistant


def _delete_assistant(model, assistants):
    client = openai.OpenAI(api_key=model["api_key"])
    removed_assistants = base_checkbox_menu(assistants, " Assistant removal:")
    for assistant in removed_assistants:
        assistant_path = os.path.join(ASSISTANTS_PATH, decapitalize(assistant) + ".json")
        with open(assistant_path, "r") as file:
            data = json.load(file)
        assistant_id = data["assistant_id"]
        thread_id = data["thread_id"]
        response = client.beta.assistants.delete(assistant_id)
        custom_print("info", str(response))
        try:
            response = client.beta.threads.delete(thread_id)
            custom_print("info", str(response))
        except openai.NotFoundError as e:
            custom_print("error", str(e))
        os.remove(assistant_path)
        custom_print("info", f"Assistant {assistant_path}  successfully deleted.")


# Threads
## Create thread


def _create_thread(model) -> str:
    client = openai.OpenAI(api_key=model["api_key"])
    thread = client.beta.threads.create()
    return thread.id


## Retrieve thread
## Modify thread
## Delete thread

# Messages
## Create message


def create_message(client, thread_id, user_input):
    message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=user_input)
    return message


## List message


def update_conversation(client, conversation, thread_id):
    messages = (client.beta.threads.messages.list(thread_id),)
    messages_list = [
        {"id": message.id, "content": content.text.value}
        for message in messages[0].data
        for content in message.content
        if content.type == "text"
    ]
    messages_list.reverse()
    # Find the index of the dictionary with the specified id
    index = next((i for i, message in enumerate(messages_list) if message["id"] == conversation), None)
    # Slice the list from the next index to the end if the index was found
    new_messages = messages_list[index + 1 :] if index is not None else []
    # Get the 'id' of the last item in the filtered list if it's not empty
    conversation = messages_list[-1]["id"] if new_messages else None
    # Reverse the list
    return (conversation, new_messages)


## Retrieve message
## Modify message
## Delete message

# Runs


def run_thread(client, assistant_id, thread_id):
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )
        # Step 5: Check the Run status
        start_time = time.time()
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            match run.status:
                case "requires_action":
                    tool_outputs = []
                    try:
                        get_available_tools()
                    except MCPToolError:
                        custom_print("warn", "MCP servers not initialized. Initializing...")
                        initialize_tools()
                    for tool in run.required_action.submit_tool_outputs.tool_calls:
                        try:
                            markdown_print(f"> Triggered: `{tool.function.name}`.")
                            tool_outputs.append(
                                {
                                    "tool_call_id": tool.id,
                                    "output": str(call_tool(tool.function.name, json.loads(tool.function.arguments))),
                                }
                            )
                        except Exception as e:
                            run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                            raise
                    if tool_outputs:
                        try:
                            run = client.beta.threads.runs.submit_tool_outputs_and_poll(
                                thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs
                            )
                            custom_print("info", "Tool outputs submitted successfully.")
                        except Exception as e:
                            custom_print("error", f"Failed to submit tool outputs: {e}")
                            run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                            break
                    else:
                        custom_print("info", "No tool outputs to submit.")
                    continue
                case "expired":
                    custom_print("error", "Maximum wait time exceeded, please try again.")
                    break
                case "cancelled":
                    custom_print("error", "Request interrupted, please submit a new one.")
                    break
                case "failed":
                    custom_print("error", run.last_error)
                    break
                case "incomplete":
                    custom_print("error", "Run ended due to max_prompt_tokens or max_completion_tokens reached.")
                    break
                case _:
                    continue
            time.sleep(2)
            current_time = time.time()
            if (current_time - start_time) > TIMEOUT:
                custom_print("error", "Maximum wait time exceeded")
                run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                break  # Exit the loop if more than 5 minutes have passed
            continue
        return
    except KeyboardInterrupt:
        run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
        # Notifying the user about the interrupt but continues normally.
        custom_print("info", "Interrupted the request. Continue normally.")
    except openai.BadRequestError as e:
        custom_print("error", str(e))
    except Exception as e:
        custom_print("error", f"Unexpected error: {str(e)}")


## Create run
## Create thread and run
## Retrieve run
## Modify run
## Submit tool outputs to run
## Cancel a run

# Vector Stores
## Create vector store
## List vector store
## Retrieve vector store
## Modify vector store
## Delete vector store

# Vector Store Files
## Create vector store file
## List vector store files
## Retrieve vector store file
## Delete vector store file

# Vector Store File Batches
## Create vector store file batch
## Retrieve vector store file batch
## List vector store files in a batch
## Delete vector store file
