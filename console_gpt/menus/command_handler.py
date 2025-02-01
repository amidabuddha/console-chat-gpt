from typing import Optional

from console_gpt.custom_stdout import custom_print, markdown_print
from console_gpt.general_utils import help_message
from console_gpt.menus.chat_manager import chat_manager
from console_gpt.menus.settings_menu import settings_menu
from console_gpt.menus.tools_menu import tools_menu
from console_gpt.prompts.file_prompt import file_prompt
from console_gpt.prompts.image_prompt import upload_image
from console_gpt.prompts.multiline_prompt import multiline_prompt
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.url_prompt import additional_info, input_url
from console_gpt.scrape_page import page_content


def command_handler(model_title, model_name, user_input, conversation, cached) -> Optional[str]:
    """
    Handled specific keywords as features if entered by the user
    :return: None or modified user input string or hint for the caller function loop or exits the application
    """

    match user_input.lower():
        case "help" | "commands":
            help_message()
            return "continue"
        case "cost":
            custom_print("warn", "Cost calculation is not yet implemented")
            return "continue"
        case "edit":
            custom_print("warn", "Edit last message is not yet implemented")
            return "continue"
        case "tools":
            return "continue", tools_menu()
        case "file":
            clarification, file_data = file_prompt()
            if not file_data:
                return "continue"
            if not clarification:
                if cached is True:
                    user_input = "This is the content of a file.", file_data
                else:
                    user_input = file_data
            else:
                if cached is True:
                    user_input = clarification, file_data
                else:
                    user_input = f"{clarification}:\n{file_data}"
            return user_input
        case "format":
            clarification, multiline_data = multiline_prompt()
            if not multiline_data:
                return "continue"
            if not clarification:
                if cached is True:
                    user_input = (
                        "Please review the multiline input and perform the requested actions or answer.",
                        multiline_data,
                    )
                else:
                    user_input = multiline_data
            else:
                markdown_print(clarification, header="Prompt clarifications", header_color="yellow", end="\n")
                if cached is True:
                    user_input = clarification, multiline_data
                else:
                    user_input = f"{clarification}:\n{multiline_data}"
            return user_input
        case "flush" | "new":
            # simply breaks this loop (inner) which start the outer one
            save_chat(conversation, ask=True, skip_exit=True)
            return "break"
        case "chats":
            chat_manager()
            return "continue"
        case "settings":
            settings_menu()
            return "continue"
        case "save":
            save_chat(conversation, skip_exit=True)
            return "continue"
        case "browser":
            web_content, success = page_content(input_url())
            if success:
                clarification, webpage_data = additional_info(web_content)
                if not clarification:
                    if cached is True:
                        user_input = "This is the content of a webpage.", webpage_data
                    else:
                        user_input = webpage_data
                else:
                    if cached is True:
                        user_input = clarification, webpage_data
                    else:
                        user_input = f"{clarification}:\n{webpage_data}"
                return user_input
            return "continue"
        case "image":
            if model_title.lower().startswith(('mistral', 'o1-mini', 'o1-preview')):
                custom_print(
                    "error",
                    f"Cannot upload images unless you're using vision supported model. Current model: {model_name}!",
                )
                return "continue"
            if model_title.lower().startswith("anthropic") and cached is True:
                custom_print(
                    "error",
                    f"Cannot upload images into Anthropic Prompt Cache",
                )
                return "continue"
            return upload_image(model_title)
        case "exit" | "quit" | "bye":
            save_chat(conversation, ask=True)

        case _:
            if cached is True:
                return user_input, str(cached)
            else:
                return user_input
