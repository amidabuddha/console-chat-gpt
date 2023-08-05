import os
import openai
import sys
from termcolor import colored
import signal
import locale

USER_PROMPT_COLOR = "blue"
ASSISTANT_PROMPT_COLOR = "yellow"
ASSISTANT_RESPONSE_COLOR = "cyan"
CHAT_MODEL = "gpt-3.5-turbo"
CHAT_MODEL_PRICING_PER_1K = 0.0015
CODE_COLOR = "red"
CODE_BACKGROUND = None

locale.setlocale(locale.LC_ALL, "")


def signal_handler(sig, frame):
    print(colored("\n[WARN] You pressed Ctrl+C! Bye!", "yellow"))
    sys.exit(0)


def error_msg(text: str) -> None:
    print(colored(text, "red"))
    sys.exit(1)


def coloring_for_code(
        text: str, color: str, on_color: (str, None), signal: bool = False, is_skip=False
):
    if signal and not is_skip:
        return colored(text, color, on_color)
    if is_skip:
        return ""
    return colored(text, ASSISTANT_RESPONSE_COLOR)


def clean_up(data: list) -> list:
    return [x for x in data if x]


def handle_code(text: str) -> str:
    words = text.split("\n")
    result = []
    enable_color = False
    skip_shit = False
    for word in words:
        if word.startswith("```python") or word.startswith("```"):
            enable_color = True if not enable_color else False
            skip_shit = True if not skip_shit else False
        result.append(
            coloring_for_code(
                word, CODE_COLOR, CODE_BACKGROUND, enable_color, skip_shit
            )
        )
        skip_shit = False
    result = clean_up(result)
    return "\n".join(result)


def prettify(text: str, color: str, assistant: bool = False) -> str:
    if assistant:
        return (
            f"{colored('Assistant:', ASSISTANT_PROMPT_COLOR, attrs=['bold', 'underline'])} "
            f"{colored(text, color)}\n"
        )
    return colored(text, color, attrs=["bold"])


def chat():
    if not os.getenv("OPENAI_API_KEY"):
        error_msg("[ERROR] API key is missing, please refer to README.md!")

    openai.api_key = os.getenv("OPENAI_API_KEY")
    default_system_role = "You are a helpful assistant."
    custom_system_role = input(
        "Define assistant bahavior or press 1 for the default setting: "
    )

    if custom_system_role == "1":
        system_role = default_system_role
    else:
        system_role = custom_system_role

    conversation = [{"role": "system", "content": system_role}]
    conversation_tokens = 0

    while True:
        user_prompt = input(prettify("User: ", USER_PROMPT_COLOR))
        if user_prompt.lower() in ("exit", "quit", "bye"):
            break

        user_message = {"role": "user", "content": user_prompt}
        conversation.append(user_message)
        response = openai.ChatCompletion.create(
            model=CHAT_MODEL, messages=conversation
        )
        assistant_message = response.choices[0].message
        assistant_response = {
            "role": "assistant",
            "content": assistant_message["content"],
        }
        conversation.append(assistant_response)
        print(
            prettify(
                f"{handle_code(assistant_message['content'])}",
                ASSISTANT_RESPONSE_COLOR,
                True,
            )
        )
        conversation_tokens += response.usage.total_tokens
        conversation_cost = locale.currency((conversation_tokens * CHAT_MODEL_PRICING_PER_1K / 1000), grouping=True)
        print(
            f"Tokens used: {colored(str(conversation_tokens), 'yellow')};"
            f" Chat cost: {colored(conversation_cost, 'green')}"
        )


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    chat()
    signal.pause()
