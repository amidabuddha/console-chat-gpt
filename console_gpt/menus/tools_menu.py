from unichat import UnifiedChatApi

from console_gpt.menus.skeleton_menus import (base_multiselect_menu,
                                              preview_multiselect_menu)
from mcp_servers.mcp_tcp_client import MCPClient


def tools_menu(tools):
    parent_menu_items = ["Disable all tools", "Select some tools", "Return without changes"]
    parent_selection = base_multiselect_menu("Main Tools Menu", parent_menu_items, "Tool Selection Options", exit=False)

    if "Disable all tools" in parent_selection:
        return []
    elif "Return without changes" in parent_selection:
        return tools
    elif "Select some tools" in parent_selection:
        with MCPClient() as mcp:
            tools = mcp.get_available_tools()
        menu_items = [
            {
                "label": str(tool.get("name", "Unknown")),
                "preview": str(tool.get("description", "No description available")),
            }
            for tool in tools
        ]
        selected_tools = preview_multiselect_menu(menu_items, "Tools menu", preview_title="Tool description")
        return [tool for tool in tools if tool["name"] in selected_tools] if selected_tools else []


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


def response_tools(tools):
    helper = UnifiedChatApi(api_key="")
    transformed_tools = helper._api_helper.transform_tools(helper._api_helper.normalize_tools(tools))
    opeanai_tools = []
    for tool in transformed_tools:
        opeanai_tools.append({"type": tool["type"], **tool["function"]})
    return opeanai_tools
