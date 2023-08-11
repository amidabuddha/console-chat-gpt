import json
import locale
import os
import sys

import openai
import toml
from termcolor import colored

import helpers
import styling

# Load the config file
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_PATH, "config.toml")
CHATS_PATH = os.path.join(BASE_PATH, "chats")

if not os.path.exists(CONFIG_PATH):
    styling.custom_print("error", 'Please use the "config.toml.sample" to create your configuration.', 2)

if not os.path.exists(CHATS_PATH):
    os.mkdir(CHATS_PATH)

# Conversation settings
config = toml.load(helpers.check_exist(CONFIG_PATH))
ALL_ROLES: dict = config["chat"]["roles"]
DEFAULT_ROLE = config["chat"]["default_system_role"]
DEBUG = config["chat"]["debug"]
SHOW_ROLE_SELECTION = config["chat"]["role_selector"]
SHOW_TEMPERATURE_PICKER = config["chat"]["adjust_temperature"]
SAVE_CHAT_ON_EXIT = config["chat"]["save_chat_on_exit"]

# Color settings
USER_PROMPT_COLOR = config["colors"]["user_prompt"]
ASSISTANT_PROMPT_COLOR = config["colors"]["assistant_prompt"]
ASSISTANT_RESPONSE_COLOR = config["colors"]["assistant_response"]
CODE_COLOR = config["colors"]["code"]

# API settings
API_TOKEN = helpers.fetch_api_token(config["chat"]["api_token"], CONFIG_PATH)
CHAT_MODEL = config["chat"]["model"]["model_name"]
CHAT_TEMPERATURE = config["chat"]["temperature"]
CHAT_MODEL_INPUT_PRICING_PER_1K = config["chat"]["model"]["model_input_pricing_per_1k"]
CHAT_MODEL_OUTPUT_PRICING_PER_1K = config["chat"]["model"]["model_output_pricing_per_1k"]

try:
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "en_US.utf8")
    except locale.Error:
        styling.custom_print("error",
                             'Failed to set locale. Please add either en_US.UTF-8 or en_US.utf8 to your system.', 2)


def chat():
    chat_temperature = CHAT_TEMPERATURE
    openai.api_key = API_TOKEN
    continue_chat = helpers.continue_chat_menu(CHATS_PATH)
    if continue_chat:
        conversation = continue_chat
    else:
        if SHOW_ROLE_SELECTION:
            role = helpers.roles_chat_menu(ALL_ROLES, DEFAULT_ROLE)
        else:
            role = ALL_ROLES[DEFAULT_ROLE]
        conversation = [{"role": "system", "content": role}]
        if SHOW_TEMPERATURE_PICKER:
            chat_temperature = helpers.handle_temperature(CHAT_TEMPERATURE)
        else:
            chat_temperature = CHAT_TEMPERATURE

    conversation_tokens = 0
    conversation_prompt_tokens = 0
    conversation_completions_tokens = 0

    while True:
        try:
            user_input = input(styling.coloring(USER_PROMPT_COLOR, None, user="", kattrs=["bold", "underline"]))
        except KeyboardInterrupt:
            print()
            if SAVE_CHAT_ON_EXIT:
                helpers.save_chat(CHATS_PATH, conversation, ask=True)
            sys.exit(130)
        match user_input.lower():
            case "help" | "commands":
                helpers.help_info()
                continue
            case "cost":
                helpers.print_costs(
                    conversation_tokens,
                    conversation_prompt_tokens,
                    conversation_completions_tokens,
                    CHAT_MODEL_INPUT_PRICING_PER_1K,
                    CHAT_MODEL_OUTPUT_PRICING_PER_1K,
                    DEBUG
                )
                continue
            case "file":
                user_input = helpers.file_prompt()
                if not user_input:
                    continue
            case "format":
                user_input = helpers.format_multiline()
                if not user_input:
                    continue
            case "save":
                helpers.save_chat(CHATS_PATH, conversation)
                continue
            case "exit" | "quit" | "bye":
                if SAVE_CHAT_ON_EXIT:
                    helpers.save_chat(CHATS_PATH, conversation, ask=True)
                sys.exit(0)
            case "":
                styling.custom_print("warn", "Don't leave it empty, please :)")
                continue

        user_message = {"role": "user", "content": user_input}
        conversation.append(user_message)
        response = openai.ChatCompletion.create(
            model=CHAT_MODEL, messages=conversation, temperature=chat_temperature
        )
        assistant_message = response.choices[0].message
        assistant_response = dict(
            role="assistant", content=assistant_message["content"]
        )
        conversation.append(assistant_response)
        if DEBUG:
            with open("messages.json", "w", encoding="utf-8") as log_file:
                json.dump(conversation, log_file, indent=4, ensure_ascii=False)
        print(
            styling.coloring(
                ASSISTANT_PROMPT_COLOR,
                ASSISTANT_RESPONSE_COLOR,
                assistant=styling.handle_code_v2(assistant_message["content"], CODE_COLOR),
                kattrs=["bold", "underline"],
            )
        )

        conversation_tokens += response.usage.total_tokens
        conversation_prompt_tokens += response.usage.prompt_tokens
        conversation_completions_tokens += response.usage.completion_tokens


if __name__ == "__main__":
    try:
        chat()
    except KeyboardInterrupt:
        styling.custom_print("error", "Caught interrupt!", 130)
