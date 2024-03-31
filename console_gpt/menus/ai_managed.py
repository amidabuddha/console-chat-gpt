import json
from typing import Tuple

import anthropic
import openai
from rich.console import Console

from console_gpt.catch_errors import sigint_wrapper
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
    model_name, system_prompt, user_prompt = get_model_and_prompts_based_on_conversation(assistant)
    model_data = fetch_variable("models", model_name)
    model_data.update(dict(model_title=model_name))
    model_data = update_api_key_if_placeholder(model_data)
    temperature = temperature_prompt()
    conversation = [{"role": "system", "content": system_prompt}]
    return ChatObject(model=model_data, conversation=conversation, temperature=temperature), user_prompt


def configure_assistant():
    assistant_model = fetch_variable("defaults", "assistant")
    assistant_role = fetch_variable("defaults", "assistant_role")
    model_data = fetch_variable("models", assistant_model)
    model_data.update(dict(model_title=assistant_model))
    model_data.update(dict(role=assistant_role))
    model_data = update_api_key_if_placeholder(model_data)
    return model_data


def update_api_key_if_placeholder(model_data):
    if model_data["api_key"] in ("YOUR_OPENAI_API_KEY", "YOUR_MISTRALAI_API_KEY", "YOUR_ANTHROPIC_API_KEY"):
        return set_api_key(model_data)
    return model_data


def get_client(assistant):
    """
    Get the default model based on the config
    :param assistant: Data from the config
    """
    if assistant["model_title"].startswith("gpt"):
        return openai.OpenAI(api_key=assistant["api_key"])
    elif assistant["model_title"].startswith("anthropic"):
        return anthropic.Anthropic(api_key=assistant["api_key"])


@sigint_wrapper
def send_request(client, assistant, conversation):
    if assistant["model_title"].startswith("anthropic"):
        return client.messages.create(
            model=assistant["model_name"],
            max_tokens=assistant["model_max_tokens"],
            temperature=0,
            system=assistant["role"],
            messages=conversation,
        ).model_dump_json()
    else:
        role = {"role": "system", "content": assistant["role"]}
        conversation.insert(0, role)
        return client.chat.completions.create(
            model=assistant["model_name"],
            temperature=0,
            messages=conversation,
        )


def handle_error(*args):
    for error in args:
        print(error)
    custom_print("error", "Exception was raised. Please check the error above for more information.", exit_code=1)


def parse_response(response, assistant):
    if assistant["model_title"].startswith("anthropic"):
        response = json.loads(response)
        return response["content"][0]["text"]
    return response.choices[0].message.content


def self_correction(last_reply):
    conversation = []
    fallback_prompt = (
        "Your previous response did not adhere to the specified format. "
        "Please carefully review the instructions and provide your response strictly in the "
        "specified JSON format, without any additional text or explanations outside the JSON structure."
    )
    conversation.append({"role": "assistant", "content": last_reply})
    conversation.append({"role": "user", "content": fallback_prompt})
    return conversation


def command_catcher(assistant):
    while True:
        prompt = [chat_user_prompt()]
        if prompt == [None]:  # Used to catch SIGINT
            custom_print("exit", "Goodbye, see you soon!", 130)
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


def get_model_and_prompts_based_on_conversation(assistant):
    console = Console()
    conversation = command_catcher(assistant)
    client = get_client(assistant)
    max_retries = 3
    while max_retries > 0:
        with console.status("[bold cyan]Choosing the best model for you...", spinner="aesthetic"):
            try:
                response = send_request(client, assistant, conversation)
            except (openai.APIConnectionError, anthropic.APIConnectionError) as e:
                handle_error("The server could not be reached", e.__cause__)
            except (openai.RateLimitError, anthropic.RateLimitError) as e:
                handle_error(f"A 429 status code was received; we should back off a bit. - {e}")
            except (openai.APIStatusError, anthropic.APIStatusError, anthropic.BadRequestError) as e:
                handle_error("Another non-200-range status code was received", e.status_code, e.response, e.message)
            except Exception as e:
                handle_error(f"Unexpected error: {e}")
            response = parse_response(response, assistant)
            try:
                response = json.loads(response)
                break
            except json.decoder.JSONDecodeError:
                max_retries -= 1
                custom_print("info", f"Self-correction due to incorrect format. Attempts left: {max_retries}")
                conversation.extend(self_correction(response))
                continue
    if max_retries == 0:
        custom_print("error", f"Couldn't optimise the request properly and failed. Please restart and try again.")
        custom_print("info", "Tip: Try using a different model as the default assistant.", exit_code=1)
    custom_print("info", f'System prompt: {response["messages"][0]["content"]}')
    print(conversation)
    return response["model"], response["messages"][0]["content"], conversation[-1]
