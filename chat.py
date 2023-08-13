import json
import locale
import os
import sys

import openai
import toml

import helpers
import styling

# Load the config file
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(BASE_PATH, "config.toml")
CHATS_PATH = os.path.join(BASE_PATH, "chats")

if not os.path.exists(CONFIG_PATH):
    styling.custom_print(
        "error", 'Please use the "config.toml.sample" to create your configuration.', 2
    )

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
LAST_COMPLETION_MAX_TOKENS = config["chat"]["last_completion_max_tokens"]

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
CHAT_MODEL_MAX_TOKENS = config["chat"]["model"]["model_max_tokens"]

try:
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "en_US.utf8")
    except locale.Error:
        styling.custom_print(
            "error",
            "Failed to set locale. Please add either en_US.UTF-8 or en_US.utf8 to your system.",
            2,
        )


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
    conversation_total_prompts_tokens = 0
    conversation_completion_tokens = 0
    conversation_total_completions_tokens = 0
    calculated_prompt_tokens = 0
    calculated_completion_max_tokens = CHAT_MODEL_MAX_TOKENS
    api_usage_cost = 0

    while True:
        if os.path.exists(os.path.join(BASE_PATH, "api_usage.txt")):
            with open(os.path.join(BASE_PATH, "api_usage.txt"), "r") as file:
                api_usage_cost = float(file.read())
        try:
            user_input = input(
                styling.coloring(
                    USER_PROMPT_COLOR, None, user="", kattrs=["bold", "underline"]
                )
            )
        except KeyboardInterrupt:
            if SAVE_CHAT_ON_EXIT:
                helpers.save_chat(CHATS_PATH, conversation, ask=True)
                sys.exit(130)
            styling.custom_print("error", f"Caught interrupt!", 130)
        match user_input.lower():
            case "help" | "commands":
                helpers.help_info()
                continue
            case "cost":
                helpers.print_costs(
                    conversation_tokens,
                    conversation_prompt_tokens,
                    conversation_total_prompts_tokens,
                    conversation_completion_tokens,
                    conversation_total_completions_tokens,
                    calculated_prompt_tokens,
                    calculated_completion_max_tokens,
                    CHAT_MODEL_INPUT_PRICING_PER_1K,
                    CHAT_MODEL_OUTPUT_PRICING_PER_1K,
                    api_usage_cost,
                    DEBUG,
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
        calculated_prompt_tokens = helpers.num_tokens_from_messages(
            conversation, CHAT_MODEL
        )
        calculated_completion_max_tokens = (
            CHAT_MODEL_MAX_TOKENS - calculated_prompt_tokens
        )
        if (
            calculated_prompt_tokens > CHAT_MODEL_MAX_TOKENS
            or calculated_completion_max_tokens < LAST_COMPLETION_MAX_TOKENS
        ):
            styling.custom_print(
                "error",
                "Maximum token limit for chat reached, please start a new chat",
                -1,
            )
            helpers.save_chat(CHATS_PATH, conversation, ask=True)
            sys.exit(2)
        try:
            response = openai.ChatCompletion.create(
                model=CHAT_MODEL,
                messages=conversation,
                temperature=chat_temperature,
                max_tokens=calculated_completion_max_tokens,
            )
        except openai.error.OpenAIError as e:
            styling.custom_print(
                "error", f"Unable to generate ChatCompletion:\n {e}")
            helpers.save_chat(CHATS_PATH, conversation, ask=True)
            sys.exit(1)
        assistant_message = response.choices[0].message
        assistant_response = dict(
            role="assistant", content=assistant_message["content"]
        )
        conversation.append(assistant_response)
        if DEBUG:
            with open(
                os.path.join(BASE_PATH, "messages.json"), "w", encoding="utf-8"
            ) as log_file:
                json.dump(conversation, log_file, indent=4, ensure_ascii=False)
        print(
            styling.coloring(
                ASSISTANT_PROMPT_COLOR,
                ASSISTANT_RESPONSE_COLOR,
                assistant=styling.handle_code_v2(
                    assistant_message["content"], CODE_COLOR
                ),
                kattrs=["bold", "underline"],
            )
        )

        conversation_tokens += response.usage.total_tokens
        conversation_prompt_tokens = response.usage.prompt_tokens
        conversation_total_prompts_tokens += response.usage.prompt_tokens
        conversation_completion_tokens = response.usage.completion_tokens
        conversation_total_completions_tokens += response.usage.completion_tokens
        helpers.update_api_usage(
            BASE_PATH,
            conversation_prompt_tokens,
            conversation_completion_tokens,
            CHAT_MODEL_INPUT_PRICING_PER_1K,
            CHAT_MODEL_OUTPUT_PRICING_PER_1K,
            api_usage_cost,
        )


if __name__ == "__main__":
    try:
        chat()
    except (KeyboardInterrupt, EOFError) as e:
        styling.custom_print("error", f"Caught interrupt!", 130)
