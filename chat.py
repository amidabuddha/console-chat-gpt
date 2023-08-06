import json
import locale
import os
import shutil
import signal
import sys
from datetime import datetime

import openai
import toml
from termcolor import colored


def fetch_api_token() -> str:
    token: str = chat_section.get("api_token")
    if token:
        return token
    error_msg(f"Please make sure that the API token is inside {CONFIG_PATH}")


def check_exist(path: str) -> str:
    if os.path.isfile(path):
        return path
    error_msg(f"No such file as - {path}")


# Load the config file
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_PATH, "config.toml")

config = toml.load(check_exist(CONFIG_PATH))

# Config Sections
chat_section = config["chat"]
colors_section = config["colors"]

# Color settings
USER_PROMPT_COLOR = colors_section.get("user_prompt")
ASSISTANT_PROMPT_COLOR = colors_section.get("assistant_prompt")
ASSISTANT_RESPONSE_COLOR = colors_section.get("assistant_response")
CODE_COLOR = colors_section.get("code")

# Model settings
API_TOKEN = fetch_api_token()
CHAT_MODEL = chat_section.get("model")
CHAT_TEMPERATURE = float(chat_section.get("temperature"))
CHAT_MODEL_INPUT_PRICING_PER_1K = float(chat_section.get("model_input_pricing_per_1k"))
CHAT_MODEL_OUTPUT_PRICING_PER_1K = float(
    chat_section.get("model_output_pricing_per_1k")
)

locale.setlocale(locale.LC_ALL, "")


def signal_handler(sig, frame) -> None:
    """
    Handle ctrl+c (SIGINT) rather than crash
    """
    print(colored("\n[WARN] You pressed Ctrl+C! Bye!", "yellow"))
    sys.exit(0)


def coloring(*colors, **data) -> (str, None):
    kattrs = data.pop("kattrs", None)  # Key attributes
    vattrs = data.pop("vattrs", None)  # Value attributes

    for key, value in data.items():
        key = " ".join(key.split("_")) if key.count("_") else key
        if len(data.keys()) == 1:
            return f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        print(
            f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        )


def code_coloring(text: str, color: str, on_color: bool = False, skip=False):
    if on_color and not skip:
        return colored(text, color)
    if skip:
        return ""
    return colored(text, ASSISTANT_RESPONSE_COLOR)


def error_msg(text: str) -> None:
    print(colored(f"[ERROR] {text}", "red"))
    sys.exit(1)


def info_msg(text: str) -> str:
    return colored(text, "blue")


def handle_code(text: str) -> str:
    result = []
    words = text.split("\n")
    enable_color = False
    skip_add = False
    for word in words:
        if word.startswith("```"):
            enable_color = True if not enable_color else False
            skip_add = True if not skip_add else False
        result.append(code_coloring(word, CODE_COLOR, enable_color, skip_add))
        skip_add = False
    return "\n".join([x for x in result if x])


def custom_input(prompt: str) -> str:
    while True:
        data = input(prompt)
        if data:
            if data.lower() in ("exit", "quit", "bye"):
                save_chat()
                sys.exit(0)
            return data
        print(coloring("yellow", "red", warning="Don't leave it empty, please :)"))


def print_costs(
    used_tokens, conversation_prompt_tokens, conversation_completions_tokens
):
    conversation_prompt_cost = (
        conversation_prompt_tokens * CHAT_MODEL_INPUT_PRICING_PER_1K / 1000
    )
    conversation_completions_cost = (
        conversation_completions_tokens * CHAT_MODEL_OUTPUT_PRICING_PER_1K / 1000
    )
    conversation_cost = locale.currency(
        (conversation_prompt_cost + conversation_completions_cost), grouping=True
    )
    coloring(None, "green", tokens_used=used_tokens, chat_cost=conversation_cost)


def save_chat():
    save_chat = input(
        info_msg(
            "Press 'ENTER' to quit or 's' to save this chat to the current directory."
        )
    )
    if save_chat.lower() == "s":
        file_name = "messages.json"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_chat = f"{os.path.splitext(file_name)[0]}_{timestamp}{os.path.splitext(file_name)[1]}"
        shutil.copy(file_name, saved_chat)
        print(f"Chat conversation saved to {saved_chat}")


def chat():
    openai.api_key = API_TOKEN
    continue_chat = input(
        info_msg(
            "Press 'ENTER' for a new chat, or the full name of the json file holding previous messages list: "
        )
    )
    if continue_chat:
        while True:
            if not continue_chat.endswith(".json"):
                continue_chat += ".json"
            file_path = os.path.join(BASE_PATH, continue_chat)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r") as file:
                        conversation = json.load(file)
                        break
                except json.JSONDecodeError as e:
                    print("Error decoding JSON:", e)
                    sys.exit(1)
                except Exception as e:
                    print("Error:", e)
                    sys.exit(1)
            else:
                continue_chat = input(
                    info_msg(
                        (
                            f"The file '{continue_chat}' does not exist in the current directory. Enter a valid file name or press 'ENTER' to abort: "
                        )
                    )
                )
                if not continue_chat:
                    sys.exit(0)
    else:
        default_system_role = config["CHAT"]["default_system_role"]
        custom_system_role = input(
            info_msg(
                "Define assistant behavior or press 'ENTER' for the default setting: "
            )
        )

        if not custom_system_role:
            system_role = default_system_role
        else:
            system_role = custom_system_role

        conversation = [{"role": "system", "content": system_role}]

    custom_temperature = input(
        info_msg(
            "Enter a value between 0 and 2 to define chat output randomness or press 'ENTER' for the default setting (1): "
        )
    )
    if not custom_temperature:
        chat_temperature = CHAT_TEMPERATURE
    else:
        try:
            chat_temperature = int(custom_temperature)
        except ValueError as e:
            try:
                chat_temperature = float(custom_temperature)
            except ValueError as e:
                print("Incorrect value:", e)
                sys.exit(1)

    conversation_tokens = 0
    conversation_prompt_tokens = 0
    conversation_completions_tokens = 0

    while True:
        user_prompt = custom_input(colored("User: ", USER_PROMPT_COLOR))
        # TODO: Replace IF statements with case and increase Python requirement to 3.10+
        if user_prompt.lower() == "cost":
            print_costs(
                conversation_tokens,
                conversation_prompt_tokens,
                conversation_completions_tokens,
            )
            continue

        if user_prompt.lower() in ["help", "commands"]:
            # TODO: Make it more comprehensive
            print("You can use the following commands:")
            print("\tcost - Display conversation costs.")
            print("\tfile - Process a file.")
            print("\texit - Exit the program.")
            continue

        if user_prompt.lower() == "file":
            skip = False
            while not skip:
                file_prompt = custom_input(
                    colored(
                        "Enter the desired filename to pass its content as prompt: ",
                        USER_PROMPT_COLOR,
                    )
                )
                file_path = os.path.join(BASE_PATH, file_prompt)

                if os.path.isfile(file_path):
                    with open(file_path, "r") as file:
                        user_prompt = file.read()
                        file.close()
                        break
                else:
                    another_try = input(
                        info_msg(
                            (
                                f"The file '{file_prompt}' does not exist in the current directory. Press ENTER to try again or any other key to abort."
                            )
                        )
                    )
                    if not another_try:
                        continue
                    else:
                        skip = True
                        break
            if skip:
                continue

        user_message = {"role": "user", "content": user_prompt}
        conversation.append(user_message)
        response = openai.ChatCompletion.create(
            model=CHAT_MODEL, messages=conversation, temperature=chat_temperature
        )
        assistant_message = response.choices[0].message
        assistant_response = dict(
            role="assistant", content=assistant_message["content"]
        )
        conversation.append(assistant_response)

        with open("messages.json", "w") as log_file:
            json.dump(conversation, log_file, indent=4)

        print(
            coloring(
                ASSISTANT_PROMPT_COLOR,
                ASSISTANT_RESPONSE_COLOR,
                assistant=handle_code(assistant_message["content"]),
            )
        )

        conversation_tokens += response.usage.total_tokens
        conversation_prompt_tokens += response.usage.prompt_tokens
        conversation_completions_tokens += response.usage.completion_tokens


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    chat()
    signal.pause()
