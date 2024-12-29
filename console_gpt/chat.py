from unichat import UnifiedChatApi

from console_gpt.catch_errors import handle_with_exceptions
from console_gpt.config_manager import fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.save_chat_prompt import save_chat
from console_gpt.prompts.user_prompt import chat_user_prompt
from console_gpt.unichat_handler import (handle_non_streaming_response,
                                         handle_streaming_response)
from mcp_servers.mcp_tcp_client import MCPClient


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

    client = UnifiedChatApi(api_key=api_key)
    conversation = data.conversation
    temperature = data.temperature
    cached = model_title.startswith("anthropic")
    if fetch_variable("features", "mcp_client"):
        with MCPClient() as mcp:
            if mcp is None:
                custom_print(
                    "error", "Could not establish connection to MCP server. Chat functionality may be limited."
                )
            else:
                tools = mcp.get_available_tools()
                custom_print("info", f"Total tools initialized: {len(tools)}", start="\n")

    else:
        tools = []

    # Inner Loop
    while True:
        response = ""  # Adding this to satisfy the IDE
        error_appeared = False  # Used when the API returns an exception
        # Check if we're not in the middle of a tool call
        if (
            not conversation
            or (
                isinstance(conversation[-1], str)
                or getattr(
                    conversation[-1],
                    "role",
                    None if isinstance(conversation[-1], str) else conversation[-1].get("role", None),
                )
            )
            != "tool"
        ):
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
                case ("continue", new_tools):
                    tools = new_tools if new_tools else []
                    custom_print("info", f"Total tools initialized: {len(tools)}", start="\n")
                    continue
                case "continue" | None:
                    continue
                case "break":
                    break
                case _:
                    if model_title.startswith("anthropic") and cached is True:
                        user_input["content"], cached = handled_user_input
                    else:
                        user_input["content"] = handled_user_input

            # Add user's input to the overall conversation
            conversation.append(user_input)

        # Get chat completion
        streaming = fetch_variable("features", "streaming")
        # Start the loading bar until API response is returned
        with console.status("[bold green]Generating a response...", spinner="aesthetic"):
            response = handle_with_exceptions(
                lambda: client.chat.completions.create(
                    model=model_name,
                    messages=conversation,
                    temperature=temperature,
                    cached=cached,
                    tools=tools,
                    stream=streaming,
                )
            )

        if response not in ["interrupted", "error_appeared"] and streaming:
            conversation = handle_with_exceptions(lambda: handle_streaming_response(model_name, response, conversation))

        if response not in ["interrupted", "error_appeared"] and not streaming:
            conversation = handle_non_streaming_response(model_name, response, conversation)
        elif response == "interrupted":
            last_user_index = next((i for i, msg in enumerate(reversed(conversation)) if msg["role"] == "user"), None)

            if last_user_index is not None:
                conversation = conversation[: len(conversation) - 1 - last_user_index]
            continue
        elif response == "error_appeared":
            error_appeared = True

        if error_appeared:
            custom_print(
                "warn",
                "Exception was raised. Decided whether to continue. Your last message is lost as well",
            )
            # Removes the last user input in order to avoid issues if the conversation continues
            if conversation:
                conversation.pop(-1)
            continue
