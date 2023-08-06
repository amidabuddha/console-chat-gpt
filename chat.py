import os
import openai
import sys
from termcolor import colored
import signal
import locale
import configparser
import json

# Global Variables
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = f"{BASE_PATH}/config.ini"
USER_PROMPT_COLOR = "blue"
ASSISTANT_PROMPT_COLOR = "yellow"
ASSISTANT_RESPONSE_COLOR = "cyan"
CHAT_MODEL = "gpt-3.5-turbo"
CHAT_MODEL_INPUT_PRICING_PER_1K = 0.0015
CHAT_MODEL_OUTPUT_PRICING_PER_1K = 0.002
CODE_COLOR = "red"

config = configparser.ConfigParser()
config.read(CONFIG_PATH)
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
        key = ' '.join(key.split('_')) if key.count("_") else key
        if len(data.keys()) == 1:
            return f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        print(f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}")


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


def fetch_token() -> str:
    if not os.getenv("OPENAI_API_KEY"):
        error_msg("API key is missing, please refer to README.md!")
    return os.getenv("OPENAI_API_KEY")


def custom_input(prompt: str) -> str:
    while True:
        data = input(prompt)
        if data:
            return data
        print(coloring("yellow", "red", warning="Don't leave it empty, please :)"))


def print_costs(used_tokens, conversation_prompt_tokens, conversation_completions_tokens):
    conversation_prompt_cost = conversation_prompt_tokens * CHAT_MODEL_INPUT_PRICING_PER_1K / 1000
    conversation_completions_cost = conversation_completions_tokens * CHAT_MODEL_OUTPUT_PRICING_PER_1K / 1000
    conversation_cost = locale.currency((conversation_prompt_cost + conversation_completions_cost), grouping=True)
    coloring(None, "green", tokens_used=used_tokens, chat_cost=conversation_cost)


def chat():
    openai.api_key = fetch_token()
    default_system_role = config["CHAT"]["default_system_role"]
    custom_system_role = input(info_msg("Define assistant behavior or press 'ENTER' for the default setting: "))

    if not custom_system_role:
        system_role = default_system_role
    else:
        system_role = custom_system_role

    conversation = [{"role": "system", "content": system_role}]
    conversation_tokens = 0
    conversation_prompt_tokens = 0
    conversation_completions_tokens = 0

    while True:
        user_prompt = custom_input(colored("User: ", USER_PROMPT_COLOR))
        # TODO: Replace IF statements with case and increase Python requirement to 3.10+
        if user_prompt.lower() in ("exit", "quit", "bye"):
            sys.exit(0)

        if user_prompt.lower() == "cost":
            print_costs(conversation_tokens, conversation_prompt_tokens, conversation_completions_tokens)
            continue

        if user_prompt.lower() in ["help", "commands"]:
            # TODO: Make it more comprehensive
            print("You can use cost and exit")
            continue

        user_message = {"role": "user", "content": user_prompt}
        conversation.append(user_message)
        response = openai.ChatCompletion.create(model=CHAT_MODEL, messages=conversation)
        assistant_message = response.choices[0].message
        assistant_response = dict(role="assistant", content=assistant_message["content"])
        conversation.append(assistant_response)

        with open('messages.json', 'w') as log_file:
            json.dump(conversation, log_file, indent=4)

        print(coloring(ASSISTANT_PROMPT_COLOR, ASSISTANT_RESPONSE_COLOR,
                       assistant=handle_code(assistant_message['content'])))

        conversation_tokens += response.usage.total_tokens
        conversation_prompt_tokens += response.usage.prompt_tokens
        conversation_completions_tokens += response.usage.completion_tokens


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    chat()
    signal.pause()
