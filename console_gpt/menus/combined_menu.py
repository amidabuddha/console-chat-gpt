from typing import Dict, List, NamedTuple

from console_gpt.constants import api_key_placeholders
from console_gpt.menus.assistant_menu import assistant_menu
from console_gpt.menus.key_menu import set_api_key
from console_gpt.menus.model_menu import model_menu
from console_gpt.menus.role_menu import role_menu
from console_gpt.menus.select_chat_menu import select_chat_menu
from console_gpt.prompts.temperature_prompt import temperature_prompt

"""
All menus at once for simplicity
"""


class ChatObject(NamedTuple):
    model: Dict
    conversation: List[Dict]
    temperature: float


class AssistantObject(NamedTuple):
    model: Dict
    assistant_name: str
    assistant_id: str
    thread_id: str


def combined_menu() -> ChatObject | AssistantObject:
    """
    Call all menus and generate an Object based on the user actions during
    his journey through the menus
    :return: Returns the object
    """

    model = model_menu()
    if model.get("api_key") in api_key_placeholders:
        model = set_api_key(model)
    assistant = assistant_menu(model) if model["model_title"].lower().startswith(("gpt", "o3")) else None
    if assistant:
        return AssistantObject(
            model=model, assistant_name=assistant[0], assistant_id=assistant[1], thread_id=assistant[2]
        )
    else:
        continue_chat = select_chat_menu()
        # Ask for role only if we're not continuing any chat
        if not continue_chat:
            _, role = role_menu()
            temperature = temperature_prompt()
            # Generate a base conversation if we're not continuing any chat
            conversation = [{"role": "system", "content": role}]
            return ChatObject(model=model, conversation=conversation, temperature=temperature)
        else:
            temperature = temperature_prompt()
            conversation = continue_chat
            return ChatObject(model=model, conversation=conversation, temperature=temperature)
