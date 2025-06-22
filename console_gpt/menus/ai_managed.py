import json
from typing import Tuple

from rich.console import Console
from unichat import UnifiedChatApi

from console_gpt.catch_errors import sigint_wrapper
from console_gpt.config_manager import fetch_variable
from console_gpt.constants import api_key_placeholders
from console_gpt.custom_stdout import custom_print
from console_gpt.menus.combined_menu import ChatObject
from console_gpt.menus.command_handler import command_handler
from console_gpt.menus.key_menu import set_api_key
from console_gpt.prompts.temperature_prompt import temperature_prompt
from console_gpt.prompts.user_prompt import chat_user_prompt

MODEL_KEYS = [
    "{{assistant_generalist}}",
    "{{assistant_fast}}",
    "{{assistant_thinker}}",
    "{{assistant_coder}}",
]


def managed_prompt() -> Tuple[ChatObject, str]:
    """
    Use assistant help to determine the best model and fromat for the query
    :return: Returns a ChatObject object, along with the original user prompt
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
    assistant_model = fetch_variable("managed", "assistant")
    assistant_role = fetch_variable("managed", "assistant_role")
    replacements = {key: fetch_variable("managed", key.strip("{}")) for key in MODEL_KEYS}
    for key, value in replacements.items():
        assistant_role = assistant_role.replace(key, value)
    model_data = fetch_variable("models", assistant_model)
    model_data.update(model_title=assistant_model, role=assistant_role)
    return update_api_key_if_placeholder(model_data)


def update_api_key_if_placeholder(model_data):
    if model_data.get("api_key") in api_key_placeholders:
        return set_api_key(model_data)
    return model_data


def get_client(assistant):
    """
    Init the client
    :param assistant: Data from the config
    """
    assistant_params = {"api_key": assistant["api_key"]}
    if assistant["base_url"]:
        assistant_params["base_url"] = assistant["base_url"]
    return UnifiedChatApi(**assistant_params)


def get_tools_schema():
    """
    Dynamically generate the tools schema with the current model names from config.
    """
    model_names = [fetch_variable("managed", key.strip("{}")) for key in MODEL_KEYS]
    return [
        {
            "name": "managed_prompt",
            "description": "Selects optimal AI model and generates appropriate system instructions based on user query analysis",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "enum": model_names,
                        "description": "The selected AI model based on query analysis",
                    },
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["system"],
                                    "description": "The role of the message, only system messages are allowed",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "The system instruction for the selected AI model",
                                },
                            },
                            "required": ["role", "content"],
                        },
                        "minItems": 1,
                        "maxItems": 1,
                    },
                },
                "required": ["model", "messages"],
            },
        }
    ]


@sigint_wrapper
def send_request(client, assistant, conversation):
    if "reasoning_effort" in assistant:
        reasoning_effort = assistant["reasoning_effort"]
    else:
        reasoning_effort = False
    role = {"role": "system", "content": assistant["role"]}
    conversation.insert(0, role)
    response = client.chat.completions.create(
        model=assistant["model_name"],
        messages=conversation,
        stream=False,
        tools=get_tools_schema(),
        reasoning_effort=reasoning_effort,
    )
    return response.choices[0].message.tool_calls


def self_correction(last_reply):
    conversation = []
    fallback_prompt = (
        "Your previous response did not adhere to the specified format. "
        "Please carefully review the instructions and provide your response strictly in the "
        "specified JSON format, without any additional text or explanations outside the JSON structure."
    )
    conversation.append({"role": "assistant", "content": last_reply or "Your response was empty"})
    conversation.append({"role": "user", "content": fallback_prompt})
    return conversation


def command_catcher(assistant):
    while True:
        prompt = [chat_user_prompt()]
        if prompt == [None]:  # Used to catch SIGINT
            custom_print("exit", "Goodbye, see you soon!", 130)
        if prompt[0]["content"].lower() in ("image"):
            custom_print(
                "warn",
                f'Command {prompt[0]["content"].lower()} is available only when the conversation is already initiated!',
            )
            continue
        if prompt[0]["content"].lower() in ("tools"):
            custom_print(
                "warn",
                f"Tools are available only when the conversation is already initiated! ",
            )
            continue
        # Command Handler
        handled_prompt = command_handler(
            assistant["model_title"], assistant["model_name"], prompt[0]["content"], prompt, False, []
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
    user_prompt = conversation.copy()
    client = get_client(assistant)
    max_retries = 3
    while max_retries > 0:
        with console.status("[bold cyan]Choosing the best model for you...", spinner="aesthetic"):
            try:
                response = send_request(client, assistant, conversation)
                try:
                    response = json.loads(response[0].function.arguments)
                    break
                except (json.decoder.JSONDecodeError, TypeError):
                    max_retries -= 1
                    custom_print("info", f"Self-correction due to incorrect format. Attempts left: {max_retries}")
                    conversation.extend(self_correction(response))
                    continue
            except Exception as e:
                max_retries = 0
                custom_print("error", f"An error occurred: {e}")
    if max_retries == 0:
        custom_print("error", f"Couldn't optimise the request properly and failed. Please restart and try again.")
        custom_print("info", "Tip: Try using a different model as the default assistant.", exit_code=1)
    custom_print("info", f'System prompt: {response["messages"][0]["content"]}')
    return response["model"], response["messages"][0]["content"], user_prompt[0]
