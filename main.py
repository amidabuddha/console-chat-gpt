import openai
from rich.console import Console

from console_gpt.config_manager import check_valid_config
from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import help_message, set_locale
from console_gpt.menus.combined_menu import combined_menu
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.file_prompt import file_prompt
from console_gpt.prompts.image_prompt import upload_image
from console_gpt.prompts.multiline_prompt import multiline_prompt
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.user_prompt import user_prompt


def console_gpt() -> None:
    console = Console()  # Used for the status bar
    set_locale()
    check_valid_config()
    # Outer loop
    while True:
        data = combined_menu()  # Call the main menu with all sub-menus
        # Assign all variables at once via the Object returned by the menu
        (
            api_key,
            api_usage,
            model_input_pricing_per_1k,
            model_max_tokens,
            model_name,
            model_output_pricing_per_1k,
        ) = data.model.values()

        model_type = data.model_type

        # Initiate API
        client = openai.OpenAI(api_key=api_key)

        # Set defaults
        conversation = data.conversation
        temperature = data.temperature

        # Inner Loop
        while True:
            response = ""  # Adding this to satisfy the IDE
            error_appeared = False  # Used when the API returns an exception
            user_input = user_prompt()
            if not user_input:  # Used to catch SIGINT
                save_chat(conversation, ask=True)

            # Command Handler
            match user_input["content"].lower():
                case "help" | "commands":
                    help_message()
                    continue
                case "cost":
                    pass
                case "file":
                    user_input = file_prompt()
                case "format":
                    user_input = multiline_prompt()
                case "flush" | "new":
                    # simply breaks this loop (inner) which start the outer one
                    save_chat(conversation, ask=True, skip_exit=True)
                    break
                case "save":
                    save_chat(conversation, skip_exit=True)
                    continue
                case "image":
                    if model_type != "gpt4-vision":
                        custom_print(
                            "error",
                            f"Cannot upload images unless you're using vision supported model. Current model: {model_name}!",
                        )
                        continue
                    user_input = upload_image()
                case "exit" | "quit" | "bye":
                    save_chat(conversation, ask=True)

            # Jump to start if any of the custom commands return None
            # Rather than exiting.
            if not user_input:
                continue

            # Add user's input to the overall conversation
            conversation.append(user_input)

            # Start the loading bar until API response is returned
            with console.status("[bold green]Generating a response...", spinner="aesthetic"):
                try:
                    response = client.chat.completions.create(
                        model=model_name, temperature=temperature, messages=conversation, max_tokens=model_max_tokens
                    )
                except openai.APIConnectionError as e:
                    error_appeared = True
                    print("The server could not be reached")
                    print(e.__cause__)
                except openai.RateLimitError as e:
                    error_appeared = True
                    print(f"A 429 status code was received; we should back off a bit. - {e}")
                except openai.APIStatusError as e:
                    error_appeared = True
                    print("Another non-200-range status code was received")
                    print(e.status_code)
                    print(e.response)
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
            response = response.choices[0].message.content
            assistant_response = dict(role="assistant", content=response)
            conversation.append(assistant_response)
            assistance_reply(response)


if __name__ == "__main__":
    console_gpt()
