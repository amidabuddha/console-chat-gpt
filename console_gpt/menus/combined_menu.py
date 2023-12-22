from typing import Dict, List, NamedTuple

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


def combined_menu() -> ChatObject:
    """
    Call all menus and generate an Object based on the user actions during
    his journey through the menus
    :return: Returns the object
    """
    model = model_menu()
    continue_chat = select_chat_menu()

    # Ask for role only if we're not continuing any chat
    role = role_menu() if not continue_chat and model["model_title"] != "mistral" else None
    temperature = temperature_prompt()

    # Generate a base conversation if we're not continuing any chat
    conversation = continue_chat if continue_chat else [{"role": "system", "content": role}]
    return ChatObject(model=model, conversation=conversation, temperature=temperature)
