from console_gpt.mcp_client import get_available_tools
from console_gpt.menus.skeleton_menus import preview_multiselect_menu

def tools_menu():
    tools = get_available_tools()
    menu_items = [
        {
            "label": str(tool.get("name", "Unknown")),
            "preview": str(tool.get("description", "No description available"))
        }
        for tool in tools
    ]
    selected_tools = preview_multiselect_menu(menu_items, "Tools menu", preview_title="Tool description")
    return [tool for tool in tools if tool["name"] in selected_tools] if selected_tools else None
