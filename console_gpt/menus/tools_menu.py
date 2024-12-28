from mcp_servers.mcp_tcp_client import MCPClient
from console_gpt.menus.skeleton_menus import preview_multiselect_menu


def tools_menu():
    with MCPClient() as mcp:
        tools = mcp.get_available_tools()
    menu_items = [
        {"label": str(tool.get("name", "Unknown")), "preview": str(tool.get("description", "No description available"))}
        for tool in tools
    ]
    selected_tools = preview_multiselect_menu(menu_items, "Tools menu", preview_title="Tool description")
    return [tool for tool in tools if tool["name"] in selected_tools] if selected_tools else None


def transform_tools_selection(tools_selection, tools_definitions):
    if not tools_selection:
        return None

    result = []

    # Add code interpreter if selected
    if tools_selection.get("code_interpreter"):
        result.append({"type": "code_interpreter"})

    # Create a lookup dictionary for tools definitions
    tools_dict = {tool["name"]: tool for tool in tools_definitions}

    # Process other selected tools
    for tool_name, is_selected in tools_selection.items():
        if tool_name == "code_interpreter":
            continue

        if is_selected and tool_name in tools_dict:
            tool_def = tools_dict[tool_name]

            parameters = tool_def["inputSchema"].copy()
            if "additionalProperties" not in parameters:
                parameters["additionalProperties"] = False

            transformed_tool = {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "strict": True,
                    "parameters": parameters,
                },
            }
            result.append(transformed_tool)

    return result
