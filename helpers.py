import locale
import os
import shutil
import sys
from datetime import datetime

from termcolor import colored


def fetch_api_token(token, path) -> str:
    if not token:
        error_msg(f"Please make sure that the API token is inside {path}")
    return token


def check_exist(path: str) -> str:
    if not os.path.exists(path):
        error_msg(f"No such file as - {path}")
    return path


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
    from chat import ASSISTANT_RESPONSE_COLOR

    return colored(text, ASSISTANT_RESPONSE_COLOR)


def error_msg(text: str) -> None:
    print(colored(f"[ERROR] {text}", "red"))
    sys.exit(1)


def info_msg(text: str) -> str:
    return colored(text, "blue")


def handle_code(text: str, code_color: str) -> str:
    result = []
    words = text.split("\n")
    enable_color = False
    skip_add = False
    for word in words:
        if word.startswith("```"):
            enable_color = True if not enable_color else False
            skip_add = True if not skip_add else False
        result.append(code_coloring(word, code_color, enable_color, skip_add))
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
    conversation_tokens,
    conversation_prompt_tokens,
    conversation_completions_tokens,
    input_cost,
    output_cost,
):
    conversation_prompt_cost = conversation_prompt_tokens * input_cost / 1000
    conversation_completions_cost = conversation_completions_tokens * output_cost / 1000
    conversation_cost = locale.currency(
        (conversation_prompt_cost + conversation_completions_cost), grouping=True
    )
    coloring(
        None, "green", tokens_used=conversation_tokens, chat_cost=conversation_cost
    )


def save_chat():
    if (
        input(
            info_msg(
                "Press 'ENTER' to quit or 's' to save this chat to the current directory."
            )
        ).lower()
        == "s"
    ):
        file_name = "messages.json"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_chat = f"{os.path.splitext(file_name)[0]}_{timestamp}{os.path.splitext(file_name)[1]}"
        shutil.copy(file_name, saved_chat)
        print(f"Chat conversation saved to {saved_chat}")
