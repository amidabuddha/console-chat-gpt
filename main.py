from rich.console import Console

from console_gpt.assistant import assistant
from console_gpt.chat import chat
from console_gpt.config_manager import check_config_version, fetch_variable
from console_gpt.custom_stdin import custom_input
from console_gpt.general_utils import intro_message, set_locale
from console_gpt.menus.ai_managed import managed_prompt
from console_gpt.menus.combined_menu import (AssistantObject, ChatObject,
                                             combined_menu)
from console_gpt.prompts.save_chat_prompt import _validate_confirmation


def console_gpt() -> None:
    console = Console()  # Used for the status bar
    set_locale()
    check_config_version()
    intro_message()
    # Outer loop
    while True:
        managed_user_prompt = False
        # Covering o1 models beta limitations. More infor here: https://platform.openai.com/docs/guides/reasoning/beta-limitations
        if fetch_variable("features", "ai_managed") and not fetch_variable("defaults", "assistant") in ["o1-preview", "o1-mini"]:
            managed = custom_input(
                message="Would you like to continue in AI managed mode? (Y/N):",
                validate=_validate_confirmation,
            )
            if managed in ["y", "yes"]:
                data, managed_user_prompt = (
                    managed_prompt()
                )  # Use AI Assitant to define the conversation initialization
            else:
                data = combined_menu()  # Call the main menu with all sub-menus
        else:
            data = combined_menu()  # Call the main menu with all sub-menus
        if isinstance(data, ChatObject):
            chat(console, data, managed_user_prompt)
        elif isinstance(data, AssistantObject):
            assistant(console, data)
        else:
            # Handle unexpected return type
            raise TypeError("combined_menu() returned an unexpected type.")


if __name__ == "__main__":
    console_gpt()
