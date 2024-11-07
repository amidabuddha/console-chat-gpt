import json

import anthropic
import google.generativeai as genai
import openai
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from console_gpt.custom_stdout import custom_print
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.user_prompt import chat_user_prompt


def mistral_messages(message_dicts):
    return [ChatMessage(role=msg["role"], content=msg["content"]) for msg in message_dicts]


def chat(console, data, managed_user_prompt) -> None:
    cached = True
    use_beta = False
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

    # Extract the system instructions from the conversation
    if model_title.startswith("anthropic") or model_title.startswith("gemini"):
        role = data.conversation[0]["content"] if data.conversation[0]["role"] == "system" else ""
    # Initiate API
    if model_title.startswith("mistral"):
        client = MistralClient(api_key=api_key)
    elif model_title.startswith("anthropic"):
        client = anthropic.Anthropic(api_key=api_key)
        cached = False
    elif model_title.startswith("grok"):
        client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    elif model_title.startswith("gemini"):
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": float(data.temperature),
        }
        client = genai.GenerativeModel(
            model_name=model_name, generation_config=generation_config, system_instruction=role,tools='code_execution'
        )
    else:
        client = openai.OpenAI(api_key=api_key)

    # Set defaults
    if model_title.startswith("anthropic") or model_title.startswith("gemini"):
        conversation = [message for message in data.conversation if message["role"] != "system"]
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
        handled_user_input = command_handler(model_title, model_name, user_input["content"], conversation, cached)
        match handled_user_input:
            case "continue" | None:
                continue
            case "break":
                break
            case _:
                if model_title.startswith("anthropic") and not cached:
                    user_input["content"], cached = handled_user_input
                    use_beta = True
                else:
                    user_input["content"] = handled_user_input

        # Add user's input to the overall conversation
        conversation.append(user_input)

        # Start the loading bar until API response is returned
        with console.status("[bold green]Generating a response...", spinner="aesthetic"):
            try:
                if model_title.startswith("mistral"):
                    response = client.chat(
                        model=model_name,
                        temperature=float(temperature) / 2,
                        messages=mistral_messages(conversation),
                    )
                elif model_title.startswith("anthropic"):
                    if use_beta:
                        response = client.beta.prompt_caching.messages.create(
                            model=model_name,
                            max_tokens=model_max_tokens,
                            temperature=float(temperature) / 2,
                            system=[
                                {
                                    "type": "text",
                                    "text": role,
                                },
                                {"type": "text", "text": cached, "cache_control": {"type": "ephemeral"}},
                            ],
                            messages=conversation,
                        ).model_dump_json()
                    else:
                        response = client.messages.create(
                            model=model_name,
                            max_tokens=model_max_tokens,
                            temperature=float(temperature) / 2,
                            system=role,
                            messages=conversation,
                        ).model_dump_json()
                elif model_title.startswith("gemini"):
                    output_list = []
                    for item in conversation:
                        if item["role"] == "assistant":
                            item["role"] = "model"
                        new_item = {"role": item["role"], "parts": [item["content"]]}
                        output_list.append(new_item)
                    chat_session = client.start_chat(history=output_list.pop(-1))
                    response = chat_session.send_message(handled_user_input)
                else:  # OpenAI + Grok
                    response = client.chat.completions.create(
                        model=model_name,
                        temperature=float(temperature),
                        messages=conversation,
                    )
            # TODO: Handle mistralai.exceptions.MistralAPIException
            except (openai.APIConnectionError, anthropic.APIConnectionError) as e:
                error_appeared = True
                print("The server could not be reached")
                print(e.__cause__)
            except (openai.RateLimitError, anthropic.RateLimitError) as e:
                error_appeared = True
                print(f"A 429 status code was received; we should back off a bit. - {e}")
            except (openai.APIStatusError, anthropic.APIStatusError, anthropic.BadRequestError) as e:
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
        elif model_title.startswith("gemini"):
            response = response.text
        else:
            response = response.choices[0].message.content
        assistant_response = dict(role="assistant", content=response)
        conversation.append(assistant_response)
        assistance_reply(response, model_name)
