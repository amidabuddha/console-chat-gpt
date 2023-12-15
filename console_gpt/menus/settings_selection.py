from console_gpt.config_manager import fetch_variable
from console_gpt.menus.skeleton_menus import base_settings_menu


def settings_menu():
    # TODO: WIP
    menu_data = fetch_variable("features")
    menu_title = " Control Features"
    return base_settings_menu(menu_data, menu_title)
