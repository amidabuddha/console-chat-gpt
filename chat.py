import json
import locale
import os
import signal
import sys

import openai
import toml
from termcolor import colored

import helpers
import styling

# Load the config file
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_PATH, "config.toml")

config = toml.load(helpers.check_exist(CONFIG_PATH))

# Color settings
USER_PROMPT_COLOR = config["colors"]["user_prompt"]
ASSISTANT_PROMPT_COLOR = config["colors"]["assistant_prompt"]
ASSISTANT_RESPONSE_COLOR = config["colors"]["assistant_response"]
CODE_COLOR = config["colors"]["code"]

# Model settings
API_TOKEN = helpers.fetch_api_token(config["chat"]["api_token"], CONFIG_PATH)
CHAT_MODEL = config["chat"]["model"]
CHAT_TEMPERATURE = config["chat"]["temperature"]
CHAT_MODEL_INPUT_PRICING_PER_1K = config["chat"]["model_input_pricing_per_1k"]
CHAT_MODEL_OUTPUT_PRICING_PER_1K = config["chat"]["model_output_pricing_per_1k"]

locale.setlocale(locale.LC_ALL, "")


def chat():
    openai.api_key = API_TOKEN
    continue_chat = input(
        styling.info_msg(
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
                    styling.info_msg(
                        (
                            f"The file '{continue_chat}' does not exist in the current directory. Enter a valid file name or press 'ENTER' to abort: "
                        )
                    )
                )
                if not continue_chat:
                    sys.exit(0)
    else:
        default_system_role = config["chat"]["default_system_role"]
        custom_system_role = input(
            styling.info_msg(
                "Define assistant behavior or press 'ENTER' for the default setting: "
            )
        )

        if not custom_system_role:
            system_role = default_system_role
        else:
            system_role = custom_system_role

        conversation = [{"role": "system", "content": system_role}]

    custom_temperature = input(
        styling.info_msg(
            "Enter a value between 0 and 2 to define chat output randomness or press 'ENTER' for the default setting (1): "
        )
    )
    if not custom_temperature:
        chat_temperature = CHAT_TEMPERATURE
    else:
        try:
            chat_temperature = float(custom_temperature)
            if chat_temperature < 0 or chat_temperature > 2:
                print("Value outside of allowed range!")
                sys.exit(0)
        except ValueError as e:
            print("Incorrect value:", e)
            sys.exit(1)

    conversation_tokens = 0
    conversation_prompt_tokens = 0
    conversation_completions_tokens = 0

    while True:
        user_prompt = helpers.custom_input(colored("User: ", USER_PROMPT_COLOR))
        # TODO: Replace IF statements with case and increase Python requirement to 3.10+
        if user_prompt.lower() == "cost":
            helpers.print_costs(
                conversation_tokens,
                conversation_prompt_tokens,
                conversation_completions_tokens,
                CHAT_MODEL_INPUT_PRICING_PER_1K,
                CHAT_MODEL_OUTPUT_PRICING_PER_1K,
            )
            continue

        if user_prompt.lower() in ["help", "commands"]:
            # TODO: Make it more comprehensive
            print("You can use the following commands:")
            print("\tcost - Display conversation costs.")
            print("\tfile - Process a file.")
            print("\texit - Exit the program.")
            print("")
            print("\thelp - Display this help message.")
            print("\tcommands - Display this list of commands.")
            continue

        if user_prompt.lower() == "file":
            skip = False
            while not skip:
                file_prompt = helpers.custom_input(
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
                        styling.info_msg(
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
            styling.coloring(
                ASSISTANT_PROMPT_COLOR,
                ASSISTANT_RESPONSE_COLOR,
                assistant=styling.handle_code(assistant_message["content"], CODE_COLOR),
            )
        )

        conversation_tokens += response.usage.total_tokens
        conversation_prompt_tokens += response.usage.prompt_tokens
        conversation_completions_tokens += response.usage.completion_tokens


if __name__ == "__main__":
    signal.signal(signal.SIGINT, helpers.signal_handler)
    chat()
    signal.pause()
