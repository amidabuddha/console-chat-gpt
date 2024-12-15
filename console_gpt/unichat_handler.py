import json

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from console_gpt.custom_stdout import markdown_print
from console_gpt.mcp_client import call_tool
from console_gpt.prompts.assistant_prompt import assistance_reply


def handle_streaming_response(model_name, response_stream, conversation):
    """Handle streaming response and tool calls."""
    if (
        isinstance(conversation[-1], str)
        or getattr(
            conversation[-1], "role", None if isinstance(conversation[-1], str) else conversation[-1].get("role", None)
        )
    ) != "tool":
        assistance_reply("", model_name)

    current_content = ""
    current_assistant_message = {
        "role": "assistant",
        "content": "",
    }

    last_tool_call_index = -1
    with Live(refresh_per_second=10) as live:
        for chunk in response_stream:
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if hasattr(delta, "content") and delta.content:
                current_content += delta.content
                current_assistant_message["content"] = current_content
                md = Markdown(current_content, code_theme="dracula")
                live.update(md)

            # Handle tool calls
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                # Initialize tool_calls if not present
                if "tool_calls" not in current_assistant_message:
                    current_assistant_message["tool_calls"] = []

                for tool_call in delta.tool_calls:
                    # If we have an ID, this is a new tool call
                    if hasattr(tool_call, "id") and tool_call.id:
                        new_tool_call = {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name if hasattr(tool_call.function, "name") else "",
                                "arguments": "",
                            },
                        }
                        current_assistant_message["tool_calls"].append(new_tool_call)
                        last_tool_call_index = len(current_assistant_message["tool_calls"]) - 1

                    # If we have arguments, append to the last tool call
                    if (
                        hasattr(tool_call, "function")
                        and hasattr(tool_call.function, "arguments")
                        and tool_call.function.arguments
                    ):
                        if last_tool_call_index >= 0:
                            current_assistant_message["tool_calls"][last_tool_call_index]["function"][
                                "arguments"
                            ] += tool_call.function.arguments

            if finish_reason:
                conversation.append(current_assistant_message)

    # Process tool calls
    if current_assistant_message.get("tool_calls"):
        for tool_call in current_assistant_message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            markdown_print(f"> Triggered: `{tool_name}`.")
            try:
                result = {
                    "role": "tool",
                    "content": str(
                        call_tool(
                            tool_call["function"]["name"], json.loads(tool_call["function"]["arguments"])
                        )
                    ),
                    "tool_call_id": tool_call["id"],
                }
                conversation.append(result)
            except Exception as e:
                raise
    return conversation


def handle_non_streaming_response(model_name, response, conversation):
    """Handle non-streaming response and tool calls."""
    assistant_response = {
        "role": "assistant",
        "content": "",
    }

    message = response.choices[0].message
    # Count tool occurances to not repeat the assistance_reply
    has_previous_tool_calls = any("tool_calls" in item for item in conversation)

    # Safely get tool_calls
    tool_calls = getattr(message, "tool_calls", None)

    # Handle content
    content = getattr(message, "content", None)
    if content:
        assistant_response["content"] = content
        # Use the boolean flag directly instead of counting
        if not has_previous_tool_calls:
            assistance_reply(content, model_name)
        else:
            markdown_print(content)

    # Handle tool calls if they exist
    if tool_calls:
        assistant_response["tool_calls"] = []
        for tool_call in tool_calls:
            # Safely get attributes using getattr
            tool_id = getattr(tool_call, "id", "")
            tool_fn = getattr(tool_call, "function", None)
            if tool_fn:
                tool_name = getattr(tool_fn, "name", "")
                tool_args = getattr(tool_fn, "arguments", "{}")

                new_tool_call = {
                    "id": tool_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": tool_args},
                }
                assistant_response["tool_calls"].append(new_tool_call)

    # Add the assistant's response to the conversation
    conversation.append(assistant_response)

    # Process tool calls if they exist
    if tool_calls:
        for tool in assistant_response.get("tool_calls"):
            tool_name = tool["function"]["name"]
            markdown_print(f"> Triggered: `{tool_name}`.")
            try:
                result = {
                    "role": "tool",
                    "content": str(call_tool(tool["function"]["name"], json.loads(tool["function"]["arguments"]))),
                    "tool_call_id": tool["id"],
                }
                conversation.append(result)
            except Exception as e:
                raise

    return conversation
