from rich.console import Console

from console_gpt.assistant import assistant
from console_gpt.chat import chat
from console_gpt.config_manager import check_config_version, check_valid_config
from console_gpt.general_utils import intro_message, set_locale
from console_gpt.menus.combined_menu import (AssistantObject, ChatObject,
                                             combined_menu)


def console_gpt() -> None:
    console = Console()  # Used for the status bar
    set_locale()
    check_valid_config()
    check_config_version()
    intro_message()
    # Outer loop
    while True:
        data = combined_menu()  # Call the main menu with all sub-menus
        if isinstance(data, ChatObject):
            chat(console, data)
        elif isinstance(data, AssistantObject):
            assistant(console, data)
        else:
            # Handle unexpected return type
            raise TypeError("combined_menu() returned an unexpected type.")


if __name__ == "__main__":
    console_gpt()
