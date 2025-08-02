import json

from rich.live import Live
from rich.markdown import Markdown

from console_gpt.custom_stdout import custom_print, markdown_print
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.image_prompt import save_image
from mcp_servers.mcp_tcp_client import MCPClient


def handle_streaming_completion(model_name, response_stream, conversation):
    """Handle streaming response and tool calls."""
    if (
        isinstance(conversation[-1], str)
        or getattr(
            conversation[-1], "role", None if isinstance(conversation[-1], str) else conversation[-1].get("role", None)
        )
    ) != "tool":
        assistance_reply("", model_name)

    reasoning_content = ""
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

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_content += delta.reasoning_content
                rmd = Markdown(reasoning_content, code_theme="dracula")
                live.update(rmd)

            if hasattr(delta, "content") and delta.content:
                current_content += delta.content
                current_assistant_message["content"] = current_content
                formatted_content = (
                    f"{reasoning_content}\n\n\n***** **REASONING END** *****\n\n\n{current_content}"
                    if reasoning_content
                    else current_content
                )
                md = Markdown(formatted_content, code_theme="dracula")
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
            function_arguments = tool_call["function"]["arguments"]
            if function_arguments:
                tool_arguments = json.loads(function_arguments)
            else:
                tool_arguments = {}
            markdown_print(f"> Triggered: `{tool_name}`.")
            try:
                with MCPClient() as mcp:
                    result = {
                        "role": "tool",
                        "content": str(mcp.call_tool(tool_name, tool_arguments)),
                        "tool_call_id": tool_call["id"],
                    }
                conversation.append(result)
            except Exception as e:
                custom_print("error", f"Error calling tool: {e}")
                result = {
                    "role": "tool",
                    "content": str(e),
                    "tool_call_id": tool_call["id"],
                }
                conversation.append(result)
    return conversation


def handle_non_streaming_completion(model_name, response, conversation):
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

    # Handle reasoning content
    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content:
        assistance_reply(reasoning_content, f"{model_name} Reasoning")

    # Handle content
    content = getattr(message, "content", None)
    if not content and not has_previous_tool_calls:
        assistance_reply("", model_name)
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
        for tool_call in assistant_response.get("tool_calls"):
            tool_name = tool_call["function"]["name"]
            function_arguments = tool_call["function"]["arguments"]
            if function_arguments:
                tool_arguments = json.loads(function_arguments)
            else:
                tool_arguments = {}
            markdown_print(f"> Triggered: `{tool_name}`.")
            try:
                with MCPClient() as mcp:
                    result = {
                        "role": "tool",
                        "content": str(mcp.call_tool(tool_name, tool_arguments)),
                        "tool_call_id": tool_call["id"],
                    }
                conversation.append(result)
            except Exception as e:
                custom_print("error", f"Error calling tool: {e}")
                result = {
                    "role": "tool",
                    "content": str(e),
                    "tool_call_id": tool_call["id"],
                }
                conversation.append(result)

    return conversation


def handle_streaming_response(model_name, response_stream, conversation):
    """Handle streaming response and tool calls."""
    if isinstance(conversation[-1], str) or conversation[-1].get("type") != "function_call_output":
        assistance_reply("", model_name)

    reasoning_content = ""
    current_content = ""

    with Live(refresh_per_second=10) as live:
        for event in response_stream:

            if event.type == "response.reasoning_summary_text.delta":
                reasoning_content += event.delta
                rmd = Markdown(reasoning_content, code_theme="dracula")
                live.update(rmd)

            if event.type == "response.reasoning_summary_text.done":
                reasoning_content += "\n\n"

            if event.type == "response.output_text.delta":
                current_content += event.delta
                formatted_content = (
                    f"{reasoning_content}\n\n\n***** **REASONING END** *****\n\n\n{current_content}"
                    if reasoning_content
                    else current_content
                )
                md = Markdown(formatted_content, code_theme="dracula")
                live.update(md)

            if event.type == "response.completed":
                conversation.extend(response_parser(event.response.output))

    return conversation


def handle_non_streaming_response(model_name, response, conversation):
    """Handle non-streaming response and tool calls."""

    for output in response.output:
        # Handle reasoning content
        if output.type == "reasoning":
            assistance_reply("", f"{model_name} Reasoning")
            for summary in output.summary:
                markdown_print(summary.text)
        if output.type == "message":
            assistance_reply(output.content[0].text, model_name)

    conversation.extend(response_parser(response.output))

    return conversation


def response_parser(output):
    dict_output = []
    reasoning_output = []
    for o in output:
        if o.type not in ("message", "function_call", "image_generation_call"):
            markdown_print(f"> Triggered: `{o.type}`.")
            reasoning_output.append(o.to_dict())
        if o.type == "message":
            assistant_response = {
                "role": "assistant",
                "content": o.content[0].text,
            }
            dict_output.append(assistant_response)
        if o.type == "function_call":
            dict_output.extend(reasoning_output)
            reasoning_output = []
            dict_output.append(o.model_dump())
            tool_name = o.name
            function_arguments = o.arguments
            if function_arguments:
                tool_arguments = json.loads(function_arguments)
            else:
                tool_arguments = {}
            markdown_print(f"> Triggered: `{tool_name}`.")
            try:
                with MCPClient() as mcp:
                    result = {
                        "type": "function_call_output",
                        "call_id": o.call_id,
                        "output": str(mcp.call_tool(tool_name, tool_arguments)),
                    }
                    dict_output.append(result)
            except Exception as e:
                custom_print("error", f"Error calling tool: {e}")
                result = {
                    "type": "function_call_output",
                    "call_id": o.call_id,
                    "output": str(e),
                }
                dict_output.append(result)
        if o.type == "image_generation_call":
            image_base64 = o.result
            save_image(image_base64)
    return dict_output
