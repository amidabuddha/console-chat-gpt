from unichat.unified_chat_api import get_chat_completion, set_api_key

from console_gpt.custom_stdout import custom_print
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.user_prompt import chat_user_prompt


def chat(console, data, managed_user_prompt) -> None:
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

    set_api_key(api_key)
    conversation = data.conversation
    temperature = data.temperature
    cached = not model_title.startswith("anthropic")

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
                else:
                    user_input["content"] = handled_user_input

        # Add user's input to the overall conversation
        conversation.append(user_input)

        # Start the loading bar until API response is returned
        with console.status("[bold green]Generating a response...", spinner="aesthetic"):
            try:
                response = get_chat_completion(
                    model_name=model_name,
                    messages=conversation,
                    temperature=temperature,
                    cached=cached,
                )
            except Exception as e:
                error_appeared = True
                print(f"An error occurred: {e}")
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
        assistant_response = dict(role="assistant", content=response)
        conversation.append(assistant_response)
        assistance_reply(response, model_name)
