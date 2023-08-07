import locale
import os
import shutil
import sys
from datetime import datetime

from termcolor import colored

import styling


def fetch_api_token(token, path) -> str:
    if not token:
        styling.error_msg(f"Please make sure that the API token is inside {path}")
    return token


def check_exist(path: str) -> str:
    if not os.path.exists(path):
        styling.error_msg(f"No such file as - {path}")
    return path


def signal_handler(sig, frame) -> None:
    """
    Handle ctrl+c (SIGINT) rather than crash
    """
    print(colored("\n[WARN] You pressed Ctrl+C! Bye!", "yellow"))
    sys.exit(0)


def custom_input(prompt: str) -> str:
    while True:
        data = input(prompt)
        if data:
            if data.lower() in ("exit", "quit", "bye"):
                save_chat()
                sys.exit(0)
            return data
        print(
            styling.coloring("yellow", "red", warning="Don't leave it empty, please :)")
        )


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
    styling.coloring(
        None, "green", tokens_used=conversation_tokens, chat_cost=conversation_cost
    )


def save_chat():
    if (
        input(
            styling.info_msg(
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
