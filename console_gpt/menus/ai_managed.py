import json
from typing import Tuple

import anthropic

from console_gpt.config_manager import fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.menus.combined_menu import ChatObject
from console_gpt.menus.command_handler import command_handler
from console_gpt.menus.key_menu import set_api_key
from console_gpt.prompts.temperature_prompt import temperature_prompt
from console_gpt.prompts.user_prompt import chat_user_prompt


def managed_prompt() -> Tuple[ChatObject, str]:
    """
    Use assistant help to determine the best model and fromat for the query
    :return: Returns a ChatObject object
    """
    assistant = configure_assistant()
    model_name, system_prompt, user_prompt = get_prompt(assistant)
    model_data = fetch_variable("models", model_name)
    model_data.update(dict(model_title=model_name))
    if model_data["api_key"] in ("YOUR_OPENAI_API_KEY", "YOUR_MISTRALAI_API_KEY", "YOUR_ANTHROPIC_API_KEY"):
        model_data = set_api_key(model_data)
    temperature = temperature_prompt()
    conversation = [{"role": "system", "content": system_prompt}]
    return ChatObject(model=model_data, conversation=conversation, temperature=temperature), user_prompt


def configure_assistant():
    assistant_model = fetch_variable("defaults", "assistant")
    assistant_role = fetch_variable("defaults", "assistant_role")
    model_data = fetch_variable("models", assistant_model)
    model_data.update(dict(model_title=assistant_model))
    model_data.update(dict(role=assistant_role))
    if model_data["api_key"] == "YOUR_ANTHROPIC_API_KEY":
        model_data = set_api_key(model_data)
    return model_data


def get_prompt(assistant):
    error_appeared = False
    handled_prompt = command_catcher(assistant)
    client = anthropic.Anthropic(api_key=assistant["api_key"])
    try:
        response = client.messages.create(
            model=assistant["model_name"],
            max_tokens=assistant["model_max_tokens"],
            temperature=0,
            system=assistant["role"],
            messages=handled_prompt,
        ).model_dump_json()
    except anthropic.APIConnectionError as e:
        error_appeared = True
        print("The server could not be reached")
        print(e.__cause__)
    except anthropic.RateLimitError as e:
        error_appeared = True
        print(f"A 429 status code was received; we should back off a bit. - {e}")
    except (anthropic.APIStatusError, anthropic.BadRequestError) as e:
        error_appeared = True
        print("Another non-200-range status code was received")
        print(e.status_code)
        print(e.response)
        print(e.message)
    except Exception as e:
        error_appeared = True
        print(f"Unexpected error: {e}")
    if error_appeared:
        custom_print(
            "error", "Exception was raised. Decided whether to continue. Your last message is lost as well", exit_code=1
        )
    response = json.loads(response)
    response = response["content"][0]["text"]
    response = json.loads(response)
    return response["model"], response["messages"][0]["content"], response["messages"][1]


def command_catcher(assistant):
    while True:
        prompt = [chat_user_prompt()]
        # Command Handler
        handled_prompt = command_handler(
            assistant["model_title"], assistant["model_name"], prompt[0]["content"], prompt
        )
        match handled_prompt:
            case "continue" | None:
                continue
            case "break":
                exit(1)
            case _:
                prompt[0]["content"] = handled_prompt
                break
    return prompt
