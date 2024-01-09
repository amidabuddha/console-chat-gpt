from typing import Dict, List, NamedTuple, Optional

from console_gpt.menus.model_menu import assistant_menu, model_menu
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
  tools: Optional[List[Dict]]
  assistant_id: str
  thread_id: str
  last_message: Optional[str]

def combined_menu() -> ChatObject|AssistantObject:
    """
    Call all menus and generate an Object based on the user actions during
    his journey through the menus
    :return: Returns the object
    """

    model = model_menu()
    assistant = assistant_menu(model) if model["model_title"] in ("gpt3", "gpt4") else None
    if assistant:
        return AssistantObject(model=model,tools=assistant[3], assistant_id=assistant[0], thread_id=assistant[1], last_message=assistant[2])
    else:
        continue_chat = select_chat_menu()
        # Ask for role only if we're not continuing any chat
        if not continue_chat:
            role_title, role = role_menu() if model["model_title"] != "mistral" else (None, None)
            temperature = temperature_prompt()
            # Generate a base conversation if we're not continuing any chat
            conversation = [{"role": "system", "content": role}]
            return ChatObject(model=model, conversation=conversation, temperature=temperature)
        else:
            temperature = temperature_prompt()
            conversation = continue_chat
            return ChatObject(model=model, conversation=conversation, temperature=temperature)