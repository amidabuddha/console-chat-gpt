from typing import Optional

from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import help_message
from console_gpt.menus.settings_menu import settings_menu
from console_gpt.prompts.file_prompt import file_prompt
from console_gpt.prompts.image_prompt import upload_image
from console_gpt.prompts.multiline_prompt import multiline_prompt
from console_gpt.prompts.save_chat_prompt import save_chat


def command_handler(model_title, model_name, user_input, conversation) -> Optional[str]:  
    """
    Handled specific keywords as features if entered by the user
    :return: None or modified user input string or hint for the caller function loop or exits the application
    """              
    
    match user_input.lower():
        case "help" | "commands":
            help_message()
            return "continue"
        case "cost":
            custom_print("warn", "Cost calculation is not yet implemented", None)
            return "continue"
        case "edit":
            custom_print("warn", "Edit last message is not yet implemented", None)
            return "continue"
        case "file":
            user_input = file_prompt()
            return user_input
        case "format":
            user_input = multiline_prompt()
            return user_input
        case "flush" | "new":
            # simply breaks this loop (inner) which start the outer one
            save_chat(conversation, ask=True, skip_exit=True)
            return "break"
        case "settings":
            settings_menu()
            return "continue"
        case "save":
            save_chat(conversation, skip_exit=True)
            return "continue"
        case "image":
            if model_title != "gpt4-vision":
                custom_print(
                    "error",
                    f"Cannot upload images unless you're using vision supported model. Current model: {model_name}!",
                )
                return "continue"
            user_input = upload_image()
            return user_input
        case "exit" | "quit" | "bye":
            save_chat(conversation, ask=True)
        case _:
            return user_input