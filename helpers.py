import json
import locale
import os
import string
import sys
import toml
from datetime import datetime

import tiktoken
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from simple_term_menu import TerminalMenu
from termcolor import colored

import styling


def fetch_api_token(token: str, path: str) -> str:
    """
    Checks if the API Token has been included inside the config file:
    config.toml
    """
    if not token:
        styling.custom_print(
            "error", f"Please make sure that the API token is inside {path}", 1
        )
    return token


def check_exist(path: str) -> str:
    """
    Checks if a file exists and if it doesn't abort the program with an error
    """
    if not os.path.exists(path):
        styling.custom_print("error", f"No such file as - {path}", 1)
    return path


def calculate_costs(prompt, completion, in_cost, out_cost):
    """
    Calculates the price for the given conversation.
    """
    prompt_cost = prompt * in_cost / 1000
    completions_cost = completion * out_cost / 1000
    chat_cost = prompt_cost + completions_cost
    return prompt_cost, completions_cost, chat_cost


def print_costs(
    conversation_tokens: float,
    conversation_prompt_tokens: float,
    conversation_total_prompts_tokens: float,
    conversation_completion_tokens: float,
    conversation_total_completions_tokens: float,
    calculated_prompt_tokens: float,
    calculated_completion_max_tokens: float,
    input_cost: float,
    output_cost: float,
    api_cost: float,
    debug: bool,
):
    """
    Prints the total used tokens and price.
    """
    (
        _,
        _,
        conversation_cost,
    ) = calculate_costs(
        conversation_total_prompts_tokens,
        conversation_total_completions_tokens,
        input_cost,
        output_cost,
    )
    if debug:
        styling.coloring(
            None,
            "green",
            tokens_used=conversation_tokens,
            calculated_prompt_tokens=calculated_prompt_tokens,
            prompt_tokens_used=conversation_prompt_tokens,
            total_prompt_tokens_used=conversation_total_prompts_tokens,
            calculated_completion_max_tokens=calculated_completion_max_tokens,
            completion_tokens_used=conversation_completion_tokens,
            total_completion_tokens_used=conversation_total_completions_tokens,
            chat_cost=locale.currency(conversation_cost, grouping=True),
            api_key_usage_cost=locale.currency(api_cost, grouping=True),
        )
    else:
        styling.coloring(
            None,
            "green",
            tokens_used=conversation_tokens,
            chat_cost=locale.currency(conversation_cost, grouping=True),
            api_usage_cost=locale.currency(api_cost, grouping=True),
        )


def update_api_usage(
    path,
    conversation_prompt_tokens,
    conversation_completion_tokens,
    input_cost,
    output_cost,
    usage,
):
    """
    Calculates the total conversation expences made in the current environment.
    """
    _, _, api_usage_cost = calculate_costs(
        conversation_prompt_tokens,
        conversation_completion_tokens,
        input_cost,
        output_cost,
    )
    api_usage_cost += usage
    data = toml.load(path)
    data["chat"]["api_usage"] = float(api_usage_cost)
    with open(path, "w") as toml_file:
        toml.dump(data, toml_file)


def help_info():
    """
    Prints the available commands
    """
    commands = [
        "cost - Display conversation costs.",
        "file - Submit long text from a file to the chat.",
        "flush - Start a new conversation.",
        "format - Format multiline pasted text before sending to the chat."
        "save - Save the current conversation to a file.",
        "exit - Exit the program.",
        "",
        "help - Display this help message.",
        "commands - Display this list of commands.",
    ]
    print("You can use the following commands:")
    print("\n".join(f"\t{command}" for command in commands))


def handle_base_menu(opt: str):
    """
    Additional function to base_chat_menu()
    Handles default arguments.
    """
    match opt:
        case "Skip":
            return "Skip"
        case "Exit":
            styling.custom_print("info", "Goodbye! :)")
            sys.exit(0)
        case _:
            return opt


def base_chat_menu(title: str, default_option: str, base_options: list, add_nums: bool = True) -> str:
    """
    Base terminal menu
    :param title: Title of the terminal menu
    :param base_options: The available "clickable" options
    :param add_nums: By default if the options are < 10 they will be numerated.
    If set to False, they will have alphabetic ordering.
    :return: The selected string from the menu.
    """
    enum_options = []
    counter = 1
    letters_counter = 0
    options = [default_option] + base_options + ["Exit"]
    for opt in options:
        match opt:
            case "Skip":
                enum_options.append("[s] Skip")
            case "Exit":
                enum_options.append("[x] Exit")
            case _:
                if add_nums and len(options) < 10:
                    enum_options.append("[{}] {}".format(counter, opt))
                    counter += 1
                else:
                    letters = [
                        x for x in list(string.ascii_lowercase) if x not in ["s", "x"]
                    ]
                    enum_options.append("[{}]{}".format(
                        letters[letters_counter], opt))
                    letters_counter += 1
    terminal_menu = TerminalMenu(enum_options, title=title)
    menu_entry_index = terminal_menu.show()
    if menu_entry_index is None:
        styling.custom_print(
            "error", "Keyboard interrupt or 'hack' detected", 130)
    return handle_base_menu(options[menu_entry_index])


def handle_json_files(file: str):
    """
    Opens JSON file and handle any errors
    :params file: The path to the file
    :returns: a JSON object
    """
    try:
        with open(file, "r") as file:
            data = json.load(file)
            styling.custom_print("ok", "Successfully loaded previous chat.")
        return data
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        sys.exit(1)


def continue_chat(selected_item: str, chat_path: str):
    """
    Based on the selection in continue_chat_menu() and if there are any chats
    either returns the content or False.
    """
    if selected_item == "Skip":
        return False
    full_path = os.path.join(chat_path, selected_item)
    return handle_json_files(full_path)


def continue_chat_menu(chat_path: str):
    """
    Given a Base Path craws a subdir called "chats"
    If there are no files there, it will automatically skip
    the whole function.
    :return: a string which is later handled by continue_chat()
    """
    all_chats = os.listdir(chat_path)
    if not len(all_chats):
        return continue_chat("Skip", chat_path)
    return continue_chat(
        base_chat_menu(
            "Would you like to continue a previous chat?:", "Skip", all_chats),
        chat_path,
    )


def roles_chat_menu(path: str, roles: dict, default_role: str) -> str:
    """
    Handle the roles within the config file.
    If you don't like them, you can create your own.
    """
    roles_names = list(roles.keys())
    roles_names.remove(default_role)
    roles_names.append("Add New system behavior")
    selected_role = base_chat_menu(
        f'Select a role or use the default one "{default_role}":',
        "Default",
        roles_names,
        add_nums=False,
    )
    if selected_role == "Add New system behavior":
        try:
            custom_role = input(
                colored("Enter a detailed description of your custom role: ", "blue")
            )
            while True:
                agreement = input(
                    colored(
                        "Would you like to save this role for future use? y/n: ", "yellow"
                    )
                ).lower()
                if agreement == "n" or not agreement:
                    break
                elif agreement == "y":
                    role_name = input(
                        colored(
                            "Name the role or hit 'Enter' for default name: ", "yellow"
                        )
                    )
                    if not role_name:
                        base_name = "my_role"
                        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
                        role_name = f"{base_name}_{timestamp}"
                    else:
                        role_name = role_name
                    data = toml.load(path)
                    data["chat"]["roles"][role_name] = custom_role
                    with open(path, "w") as toml_file:
                        toml.dump(data, toml_file)
                    styling.custom_print("ok", "Custom role saved!")
                    break
            return custom_role
        except KeyboardInterrupt:
            styling.custom_print(
                "info", "Cancelled the custom role creation, continuing with the chat."
            )
    role = roles.get(selected_role)
    if not role:
        return roles.get(default_role)
    return role


def handle_temperature(default_temperature: float) -> float:
    """
    Handles the chat temperature (randomness).
    """
    temp = ""
    lines = 1
    styling.custom_print(
        "info", "Enter a value between 0 and 2 to define chat output randomness"
    )
    while True:
        try:
            temp = input(
                colored(
                    f"Press 'ENTER' for the default setting ({default_temperature}): ",
                    "blue",
                )
            )
            float_temp = float(temp)
            if 2 >= float_temp >= 0:
                lines += 1
                for line in range(lines):
                    print("\033[F\033[K", end="")
                return float(float_temp)
            lines += 1
        except ValueError:
            lines += 1
            if temp == "":
                for line in range(lines):
                    print("\033[F\033[K", end="")
                return default_temperature
            continue


def file_prompt():
    """
    Opens a custom prompt which supports tab completion.
    If a file is selected that path is being returned.
    If the function is aborted a False is returned.
    """
    try:
        while True:
            user_input = prompt("Enter a path: ", completer=PathCompleter())
            if not os.path.isfile(user_input):
                styling.custom_print("warn", f"No such file at - {user_input}")
                continue
            with open(user_input, "r") as file:
                user_prompt = file.read()
                user_prompt.replace("\n", "\\n").replace('"', '\\"')
                context = input(
                    colored(
                        "Add any additional clarification in front of the submitted text or press 'ENTER' to continue: ",
                        "blue",
                    )
                )
                if context:
                    user_prompt = context + ":\n" + user_prompt
            return user_prompt
    except KeyboardInterrupt:
        styling.custom_print(
            "info", "Cancelled the file selection, continuing with the chat."
        )
        return False


def format_multiline():
    """
    Formats a multiline chat input.
    """
    try:
        styling.custom_print(
            "info",
            "Paste the multiline text and press 'Ctrl+D' on an new empty line to continue: ",
        )
        content = sys.stdin.read()
        if content:
            content.replace("\n", "\\n").replace('"', '\\"')
            context = input(
                colored(
                    "Add any additional clarification in front of the formatted text or press 'ENTER' to continue: ",
                    "blue",
                )
            )
            if context:
                content = context + ":\n" + content
        return content
    except KeyboardInterrupt:
        styling.custom_print(
            "info", "Cancelled the multiline text, continuing with the chat."
        )


def save_chat(chat_folder: str, conversation: list, ask: bool = False, skip_exit: bool = False):
    """
    Save the current chat to a folder.
    """
    if ask:
        while True:
            agreement = input(
                colored(
                    "Would you like to save the chat before you go? y/n: ", "yellow"
                )
            ).lower()
            if agreement == "n" or not agreement:
                if not skip_exit:
                    styling.custom_print("info", "Goodbye! :)", 0)
                return
            elif agreement == "y":
                break
    chat_name = input(
        colored(
            "Name the file to save the chat or hit 'Enter' for default name: ", "yellow"
        )
    )
    if not chat_name:
        base_name = "messages"
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        file_name = f"{base_name}_{timestamp}.json"
    else:
        if not chat_name.endswith(".json"):
            file_name = chat_name + ".json"
        else:
            file_name = chat_name
    file_path = os.path.join(chat_folder, file_name)
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(conversation, file, indent=4, ensure_ascii=False)
    styling.custom_print("ok", f"File saved at - {file_path}")


def num_tokens_from_messages(messages, model):
    """
    Count the tokens of the next user propmpt
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens_per_message = 3
    tokens_per_name = 1
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3
    return num_tokens
