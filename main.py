import json
import locale
import os
import openai
import toml
from typing import Any
from termcolor import colored
import sys
import platform
from simple_term_menu import TerminalMenu
from string import ascii_lowercase
import textwrap

import readline  # Necessary for input()


class Prettify:
    @staticmethod
    def custom_print(ptype: str, text: str, exit_code: int = -1, print_now: bool = True, ) -> None | str:
        """
        Based on the ptype (Print Type) it will print messages in different color.
        If print_now is set to False it will return the colored string.
        If exit_code is set to a value different from -1 the function
        will exit the whole program.
        """
        match ptype:
            case "ok":
                formatted_text: str = colored("[OK] ", "green") + text
            case "warn":
                formatted_text: str = colored("[WARN] ", "yellow") + text
            case "info":
                formatted_text: str = colored("[INFO] ", "blue") + text
            case "error":
                formatted_text: str = colored("\n[ERROR] ", "red") + text
            case _:
                formatted_text: str = colored("\n[ERROR] ", "Wrong usage of custom_print!")

        if exit_code != -1:
            sys.exit(exit_code)

        return formatted_text if not print_now else print(formatted_text)


class FetchConfig(Prettify):
    def __init__(self):
        self.BASE_PATH: str = os.path.dirname(os.path.realpath(__file__))
        self.CONFIG_PATH: str = self.__path_exist(os.path.join(self.BASE_PATH, "config.toml"),
                                                  'Please use the "config.toml.sample" to create your configuration.')
        self.CHATS_PATH: str = self.__path_exist(os.path.join(self.BASE_PATH, "chats"), create=True)
        self.config: dict[str, Any] = toml.load(self.CONFIG_PATH)
        self.ALL_ROLES: dict = self.config["chat"]["roles"]
        self.DEFAULT_ROLE: str = self.config["chat"]["default_system_role"]
        self.DEBUG: bool = self.config["chat"]["debug"]
        self.SHOW_ROLE_SELECTION: bool = self.config["chat"]["role_selector"]
        self.SHOW_TEMPERATURE_PICKER: bool = self.config["chat"]["adjust_temperature"]
        self.SAVE_CHAT_ON_EXIT: bool = self.config["chat"]["save_chat_on_exit"]
        self.LAST_COMPLETION_MAX_TOKENS: int = self.config["chat"]["last_completion_max_tokens"]

        # Color settings
        self.USER_PROMPT_COLOR: str = self.config["chat"]["colors"]["user_prompt"]
        self.ASSISTANT_PROMPT_COLOR: str = self.config["chat"]["colors"]["assistant_prompt"]
        self.ASSISTANT_RESPONSE_COLOR: str = self.config["chat"]["colors"]["assistant_response"]
        self.CODE_COLOR: str = self.config["chat"]["colors"]["code"]

        # API settings
        self.API_TOKEN: str = self.__fetch_api_token(self.config["chat"]["api_token"], self.CONFIG_PATH)
        self.CHAT_MODEL: str = self.config["chat"]["model"]["model_name"]
        self.CHAT_TEMPERATURE: float = float(self.config["chat"]["temperature"])
        self.CHAT_MODEL_INPUT_PRICING_PER_1K: float = self.config["chat"]["model"]["model_input_pricing_per_1k"]
        self.CHAT_MODEL_OUTPUT_PRICING_PER_1K: float = self.config["chat"]["model"]["model_output_pricing_per_1k"]
        self.CHAT_MODEL_MAX_TOKENS: int = self.config["chat"]["model"]["model_max_tokens"]

    def __path_exist(self, dest_path: str, error_message: str = "", create: bool = False) -> str:
        if not os.path.exists(dest_path):
            if not create:
                self.custom_print("error", error_message, 2)
            os.mkdir(dest_path)
            self.custom_print("ok", f"Created the folder - {dest_path}")
        return dest_path

    def __fetch_api_token(self, token: str, path: str) -> str:
        """
        Checks if the API Token has been included inside the config file:
        config.toml
        """
        if not token:
            self.custom_print("error", f"Please make sure that the API token is inside {path}", 1)
        return token


class Helper(FetchConfig):
    def set_locale(self) -> None:
        match platform.system():
            case "Darwin":
                locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
            case "Linux":
                locale.setlocale(locale.LC_ALL, "en_US.utf8")
            case _:
                self.custom_print("warn", f"Unable to detect OS. Setting a default locale.")
                locale.setlocale(locale.LC_ALL, '')

    @staticmethod
    def __flush_lines(lines: int) -> None:
        for line in range(lines):
            print("\033[F\033[K", end="")

    def __role_preview(self, item: str) -> str:
        rows, columns = os.popen('stty size', 'r').read().split()
        line_length = int(columns) // 2
        wrapped_text = textwrap.wrap(self.ALL_ROLES.get(item, self.DEFAULT_ROLE), width=line_length)
        return '\n'.join(wrapped_text)

    def __base_chat_menu(self, title: str, default_option: str | list, base_options: list,
                         add_nums: bool = True) -> str:
        """
        Base terminal menu
        :param title: Title of the terminal menu
        :param default_option: Place the items which you would like to appear first here
        :param base_options: The available "clickable" options
        :param add_nums: By default if the options are < 10 they will be numerated.
        If set to False, they will have alphabetic ordering.
        :return: The selected string from the menu.
        """
        enum_options: list[str] = []
        counter: int = 1
        letters_counter: int = 0
        default_option: str | list = [default_option] if isinstance(default_option, str) else default_option
        options: list[str] = default_option + base_options + ["Exit"]
        for opt in options:
            match opt:
                case "Skip":
                    enum_options.append("[s] Skip")
                case "Exit":
                    enum_options.append("[x] Exit")
                case _:
                    if add_nums and len(options) < 10:
                        enum_options.append("[{}] {}".format(counter, opt))
                        counter += 1
                    else:
                        letters: list[str] = [x for x in list(ascii_lowercase) if x not in ["s", "x"]]
                        enum_options.append("[{}]{}".format(letters[letters_counter], opt))
                        letters_counter += 1
        terminal_menu: Any = TerminalMenu(enum_options, title=title, preview_command=self.__role_preview)
        menu_entry_index: Any = terminal_menu.show()
        selected_item: str = options[menu_entry_index]
        if menu_entry_index is None:
            self.custom_print("error", "Keyboard interrupt or attempt to break stuff ;(", 130)
        if selected_item == "Exit":
            self.custom_print("info", "Goodbye :)", 0, True)
        return selected_item



    def roles_chat_menu(self) -> str:
        """
        Handle the roles within the config file.
        If you don't like them, you can create your own.
        """
        if self.SHOW_ROLE_SELECTION:
            roles_names = list(self.ALL_ROLES.keys())
            roles_names.remove(self.DEFAULT_ROLE)
            roles_names.append("Add New system behavior")
            selected_role = self.__base_chat_menu(
                f'Select a role or use the default one "{self.DEFAULT_ROLE}":',
                "Default",
                roles_names,
                add_nums=False,
            )
            # if selected_role == "Add New system behavior":
            #     # TODO offer to save the custom role to config.toml
            #     try:
            #         return input(
            #             colored("Enter a detailed description of your custom role: ", "blue")
            #         )
            #     except KeyboardInterrupt:
            #         styling.custom_print(
            #             "info", "Cancelled the custom role creation, continuing with the chat."
            #         )
            role = self.ALL_ROLES.get(selected_role)
            if not role:
                return self.ALL_ROLES.get(self.DEFAULT_ROLE)
            return role
        return self.ALL_ROLES.get(self.DEFAULT_ROLE)

    def select_temperature(self) -> float:
        """
        Handles the chat temperature (randomness).
        """
        if self.SHOW_TEMPERATURE_PICKER:
            user_input: str = ""
            lines: int = 1
            while True:
                try:
                    user_input = input(
                        self.custom_print("info", f"Press 'ENTER' for the default setting ({self.CHAT_TEMPERATURE}): ",
                                          print_now=False))
                    float_temp: float = float(user_input)
                    if 2 >= float_temp >= 0:
                        self.__flush_lines(lines)
                        return float_temp
                except ValueError:
                    if not user_input:
                        self.__flush_lines(lines)
                        return self.CHAT_TEMPERATURE
                lines += 1
        return self.CHAT_TEMPERATURE

    def select_role(self) -> str:
        pass
        # return helpers.roles_chat_menu(self.ALL_ROLES, self.DEFAULT_ROLE) if self.SHOW_ROLE_SELECTION else \
        #     self.ALL_ROLES[self.DEFAULT_ROLE]


class ConsoleGPT(Helper):
    def __init__(self):
        super().__init__()
        self.set_locale()
        self.chat_temperature: float = self.CHAT_TEMPERATURE
        self.conversation_tokens: int = 0
        self.conversation_prompt_tokens: int = 0
        self.conversation_total_prompts_tokens: int = 0
        self.conversation_completion_tokens: int = 0
        self.conversation_total_completions_tokens: int = 0
        self.calculated_prompt_tokens: int = 0
        self.calculated_completion_max_tokens: int = self.CHAT_MODEL_MAX_TOKENS
        self.api_usage_cost: int = 0

    # def select_role(self) -> str:
    #     return helpers.roles_chat_menu(self.ALL_ROLES, self.DEFAULT_ROLE) if self.SHOW_ROLE_SELECTION else \
    #         self.ALL_ROLES[self.DEFAULT_ROLE]

    def flush_chat(self):
        pass

    def save_chat(self):
        pass

    def main(self):
        # answer = input("ASd: ")
        # self.select_temperature()
        self.roles_chat_menu()


if __name__ == '__main__':
    a = ConsoleGPT()
    a.main()
