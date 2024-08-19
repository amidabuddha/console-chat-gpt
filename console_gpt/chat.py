import json

import anthropic
import openai
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from console_gpt.custom_stdout import custom_print
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.user_prompt import chat_user_prompt
from typing import List, Dict, Union


def mistral_messages(message_dicts):
    return [
        ChatMessage(role=msg["role"], content=msg["content"]) for msg in message_dicts
    ]


def _cache_message_struct(data: str) -> Dict:
    return {"type": "text", "text": data, "cache_control": {"type": "ephemeral"}}


def antropic_cache_message(
    data_to_cache: Union[List[Dict], str], is_role: bool = False
) -> List[Dict]:
    # Enable role caching (only if above 1024 tokens by default)
    if is_role:
        return [_cache_message_struct(data_to_cache)]

    message = data_to_cache[0]
    message["content"] = [_cache_message_struct(message["content"])]
    return [message]


def antropic_handle_beta_features(client, **model_data):
    supported_beta_models = {"haiku", "sonnet"}
    model = model_data.get("model", "")
    beta_on = any(beta_model in model for beta_model in supported_beta_models)

    if len(model_data["messages"]) > 1 and beta_on:
        return client.beta.prompt_caching.messages.create(**model_data)

    if beta_on:
        # Handle system message
        system_content = model_data.get("system", "")
        model_data["system"] = [_cache_message_struct(system_content)]

        # Handle user messages
        messages = model_data.get("messages", [])
        processed_messages = []
        for message in messages:
            if message["role"] == "user":
                if isinstance(message["content"], str):
                    message["content"] = [_cache_message_struct(message["content"])]
            processed_messages.append(message)
        model_data["messages"] = processed_messages

        return client.beta.prompt_caching.messages.create(**model_data)

    return client.messages.create(**model_data)


def chat(console, data, managed_user_prompt) -> None:
    # Assign all variables at once via the Object returned by the menu
    (
        api_key,
        api_usage,
        model_input_pricing_per_1k,
        model_max_tokens,
        model_name,
        model_output_pricing_per_1k,
        model_title,
    ) = data.model.values()

    # Initiate API
    if model_title.startswith("mistral"):
        client = MistralClient(api_key=api_key)
    elif model_title.startswith("anthropic"):
        client = anthropic.Anthropic(api_key=api_key)
        role = (
            data.conversation[0]["content"]
            if data.conversation[0]["role"] == "system"
            else ""
        )
    else:
        client = openai.OpenAI(api_key=api_key)

    # Set defaults
    if model_title.startswith("anthropic"):
        conversation = [
            message for message in data.conversation if message["role"] != "system"
        ]
    else:
        conversation = data.conversation
    temperature = data.temperature

    # Inner Loop
    while True:
        response = ""  # Adding this to satisfy the IDE
        error_appeared = False  # Used when the API returns an exception
        if managed_user_prompt:
            user_input = managed_user_prompt
            managed_user_prompt = False
        else:
            user_input = chat_user_prompt()
        if not user_input:  # Used to catch SIGINT
            save_chat(conversation, ask=True)
        # Command Handler
        handled_user_input = command_handler(
            model_title, model_name, user_input["content"], conversation
        )
        match handled_user_input:
            case "continue" | None:
                continue
            case "break":
                break
            case _:
                user_input["content"] = handled_user_input

        # Add user's input to the overall conversation
        conversation.append(user_input)

        # Start the loading bar until API response is returned
        with console.status(
            "[bold green]Generating a response...", spinner="aesthetic"
        ):
            try:
                if model_title.startswith("mistral"):
                    response = client.chat(
                        model=model_name,
                        temperature=float(temperature) / 2,
                        messages=mistral_messages(conversation),
                    )
                elif model_title.startswith("anthropic"):
                    response = antropic_handle_beta_features(
                        client,
                        model=model_name,
                        max_tokens=model_max_tokens,
                        temperature=float(temperature) / 2,
                        system=role,
                        messages=conversation,
                    ).model_dump_json()
                else:
                    response = client.chat.completions.create(
                        model=model_name,
                        temperature=temperature,
                        messages=conversation,
                    )
            # TODO: Handle mistralai.exceptions.MistralAPIException
            except (openai.APIConnectionError, anthropic.APIConnectionError) as e:
                error_appeared = True
                print("The server could not be reached")
                print(e.__cause__)
            except (openai.RateLimitError, anthropic.RateLimitError) as e:
                error_appeared = True
                print(
                    f"A 429 status code was received; we should back off a bit. - {e}"
                )
            except (
                openai.APIStatusError,
                anthropic.APIStatusError,
                anthropic.BadRequestError,
            ) as e:
                error_appeared = True
                print("Another non-200-range status code was received")
                print(e.status_code)
                print(e.response)
                print(e.message)
            except Exception as e:
                error_appeared = True
                print(f"Unexpected error: {e}")
            except KeyboardInterrupt:
                # Notifying the user about the interrupt but continues normally.
                custom_print("info", "Interrupted the request. Continue normally.")
                conversation.pop(-1)
                continue
        if error_appeared:
            custom_print(
                "warn",
                "Exception was raised. Decided whether to continue. Your last message is lost as well",
            )
            # Removes the last user input in order to avoid issues if the conversation continues
            conversation.pop(-1)
            continue
        if model_title.startswith("anthropic"):
            response = json.loads(response)
            response = response["content"][0]["text"]
        else:
            response = response.choices[0].message.content
        assistant_response = dict(role="assistant", content=response)
        conversation.append(assistant_response)
        assistance_reply(response, model_name)
