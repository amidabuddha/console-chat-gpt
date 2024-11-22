import json
from typing import Dict, List, Union

import anthropic
import google.generativeai as genai
import openai
from mistralai import Mistral

from lib.models import MODELS_LIST, MODELS_MAX_TOKEN

# In case you need to use a custom model, please add it to the relevant list
anthropic_models = MODELS_LIST["anthropic_models"]
mistral_models = MODELS_LIST["mistral_models"]
openai_models = MODELS_LIST["openai_models"]
grok_models = MODELS_LIST["grok_models"]
gemini_models = MODELS_LIST["gemini_models"]

DEFAULT_MAX_TOKENS = 4096


def set_api_key(api_key):
    global _api_key
    _api_key = api_key


def get_max_tokens(model_name):
    return int(MODELS_MAX_TOKEN.get(model_name, DEFAULT_MAX_TOKENS))


def get_client(model_name, temperature, role=""):
    if not hasattr(get_client, "_api_client"):
        if model_name in mistral_models:
            client = Mistral(api_key=_api_key)
        elif model_name in anthropic_models:
            client = anthropic.Anthropic(api_key=_api_key)
        elif model_name in grok_models:
            client = openai.OpenAI(api_key=_api_key, base_url="https://api.x.ai/v1")
        elif model_name in gemini_models:
            genai.configure(api_key=_api_key)
            generation_config = {
                "temperature": float(temperature),
            }
            client = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                system_instruction=role,
                tools="code_execution",
            )
        else:
            client = openai.OpenAI(api_key=_api_key)

        get_client._api_client = client

    return get_client._api_client


def set_defaults(
    model_name,
    conversation,
    temperature,
):
    # Extract the system instructions from the conversation
    if model_name in anthropic_models or gemini_models:
        role = conversation[0]["content"] if conversation[0]["role"] == "system" else ""
        conversation = [message for message in conversation if message["role"] != "system"]
    client = get_client(model_name, temperature, role)
    return client, conversation, role


def get_chat_completion(
    model_name: str,
    messages: List[Dict[str, str]],
    temperature: str,
    use_beta: bool = False,
    cached: Union[bool, str] = True,
) -> str:
    """
    Get chat completion from various AI models.

    Args:
        model_name (str): Name of the model to use
        messages (List[Dict]): List of conversation messages
        temperature (float): Temperature for response generation
        use_beta (bool): Whether to use beta features
        cached (Union[bool, str]): Caching configuration (Anthropic only)

    Returns:
        str: The generated response

    Raises:
        ConnectionError: If unable to reach the server
        RuntimeError: If rate limit exceeded or API status error
        Exception: For unexpected errors
    """
    client, messages, role = set_defaults(
        model_name,
        messages,
        temperature,
    )
    try:
        if model_name in mistral_models:
            response = client.chat.complete(
                model=model_name,
                temperature=float(temperature),
                messages=messages,
            )
            response = response.choices[0].message.content

        elif model_name in anthropic_models:
            temperature = 1 if float(temperature) > 1 else temperature
            if use_beta:
                response = client.beta.prompt_caching.messages.create(
                    model=model_name,
                    max_tokens=get_max_tokens(model_name),
                    temperature=float(temperature),
                    system=[
                        {"type": "text", "text": role},
                        {"type": "text", "text": cached, "cache_control": {"type": "ephemeral"}},
                    ],
                    messages=messages,
                ).model_dump_json()
            else:
                response = client.messages.create(
                    model=model_name,
                    max_tokens=get_max_tokens(model_name),
                    temperature=float(temperature),
                    system=role,
                    messages=messages,
                ).model_dump_json()
            response = json.loads(response)
            response_content = response["content"][0]["text"]

        elif model_name in gemini_models:
            formatted_messages = [
                {"role": "model" if item["role"] == "assistant" else item["role"], "parts": [item["content"]]}
                for item in messages
            ]
            chat_session = client.start_chat(history=formatted_messages[:-1])
            response = chat_session.send_message(formatted_messages[-1]["parts"][0])
            response_content = response.text

        elif model_name in grok_models:
            response = client.chat.completions.create(
                model=model_name,
                temperature=float(temperature),
                messages=messages,
            )
            response_content = response.choices[0].message.content

        elif model_name in openai_models:
            response = client.chat.completions.create(
                model=model_name,
                temperature=float(temperature),
                messages=messages,
            )
            response_content = response.choices[0].message.content

        else:
            return f"Model {model_name} is curently not supported"

        return response_content

    except (openai.APIConnectionError, anthropic.APIConnectionError) as e:
        raise ConnectionError(f"The server could not be reached: {e}") from e
    except (openai.RateLimitError, anthropic.RateLimitError) as e:
        raise RuntimeError(f"Rate limit exceeded: {e}") from e
    except (openai.APIStatusError, anthropic.APIStatusError, anthropic.BadRequestError) as e:
        raise RuntimeError(f"API status error: {e.status_code} - {e.message}") from e
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}") from e
