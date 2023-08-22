import tiktoken
from console_mods.config_attrs import FetchConfig
import json
import locale
import os
import toml
from typing import Any
from termcolor import colored
import platform
from simple_term_menu import TerminalMenu
from string import ascii_lowercase
import textwrap
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
import sys
from datetime import datetime
import readline  # Necessary for input()


class Helper(FetchConfig):

    @staticmethod
    def __flush_lines(lines: int) -> None:
        """
        Flushes the given number of lines on the console
        :param lines: The number of lines to flush.
        """
        for line in range(lines):
            print("\033[F\033[K", end="")

    def __role_preview(self, item: str) -> str:
        """
        Returns a preview of the selected role inside the menu
        :param item: The role name.
        :return: The preview of the role.
        """
        rows, columns = os.popen('stty size', 'r').read().split()
        line_length: int = int(columns) // 2
        match item:
            case "Add New system behavior":
                return "Write down how you would like the AI to act like."
            case "Exit":
                return "Terminate the application."
            case "Default":
                return '\n'.join(textwrap.wrap(self.ALL_ROLES.get(self.DEFAULT_ROLE, "Unknown"), width=line_length))
            case _:
                return '\n'.join(textwrap.wrap(self.ALL_ROLES.get(item, "Unknown Option"), width=line_length))

    def __add_custom_role(self) -> str | None:
        """
        Adds a custom role and its description to the config file.
        :return: The description of the custom role.
        """
        try:
            while True:
                role_title: str = self.custom_input("Enter a title for the new role: ")
                if not role_title:
                    self.custom_print("warn", "Please fill the title!")
                    continue
                if role_title not in self.ALL_ROLES.keys():
                    break
                self.custom_print("warn", "Such role name already exists!")
                continue

            while True:
                role_desc: str = self.custom_input("Enter a detailed description of your custom role: ")
                if role_desc:
                    break
                self.custom_print("warn", "Please fill the description!")
                continue

            self.write_to_config("chat", "roles", role_title, new_value=role_desc)
            return role_desc
        except KeyboardInterrupt:
            return self.ALL_ROLES.get(self.DEFAULT_ROLE)

    @staticmethod
    def help_info() -> None:
        """
        Prints the available commands
        """
        commands: list[str] = [
            "cost - Display conversation costs.",
            "edit - Edit the latest User message. Last Assistant reply will be lost.",
            "exit - Exit the program.",
            "file - Submit long text from a file to the chat.",
            "flush - Start a new conversation.",
            "format - Format multiline pasted text before sending to the chat.",
            "save - Save the current conversation to a file.",
            "",
            "help - Display this help message.",
            "commands - Display this list of commands.",
        ]
        print("You can use the following commands:")
        print("\n".join(f"\t{command}" for command in commands))

    def set_locale(self) -> None:
        """
        Sets the locale based on the operating system.
        """
        match platform.system():
            case "Darwin":
                locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
            case "Linux":
                locale.setlocale(locale.LC_ALL, "en_US.utf8")
            case _:
                self.custom_print("warn", f"Unable to detect OS. Setting a default locale.")
                locale.setlocale(locale.LC_ALL, '')

    def write_to_config(self, *args, new_value: Any) -> None:
        """
        Writes a new value to the config file
        :param args: The keys to access the value in the config file
        :param new_value: The new value to be written
        """
        with open(self.CONFIG_PATH, 'r') as file:
            config_data: dict[str, Any] = toml.load(file)

        match len(args):
            case 2:
                config_data[args[0]][args[1]] = new_value
            case 3:
                config_data[args[0]][args[1]][args[2]] = new_value
            case _:
                self.custom_print("error", "Wrong usage of write_to_config", 1)

        with open('config.toml', 'w') as file:
            toml.dump(config_data, file)

    def base_chat_menu(self, title: str, default_option: str | list[str], base_options: list,
                       add_nums: bool = True, preview_func: Any = None) -> str:
        """
        Base terminal menu
        :param title: Title of the terminal menu
        :param default_option: The first items that will appear in the menu
        :param base_options: The rest of the options
        :param add_nums: By default if the options are < 10 they will be numerated
        :param preview_func: Accepts a function that should accept and return string which is
        used within the preview box in the menu
        :return: The selected string from the menu.
        """
        enum_options: list[str] = []
        counter: int = 1
        letters_counter: int = 0
        default_option = [default_option] if isinstance(default_option, str) else default_option
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
        if preview_func:
            terminal_menu: Any = TerminalMenu(enum_options, title=title, preview_command=preview_func)
        else:
            terminal_menu: Any = TerminalMenu(enum_options, title=title)
        menu_entry_index: Any = terminal_menu.show()
        if menu_entry_index is None:
            self.custom_print("error", "Keyboard interrupt or attempt to break stuff ;(", 130)
        selected_item: str = options[menu_entry_index]
        if selected_item == "Exit":
            self.custom_print("info", "Goodbye :)", 0, True)
        return selected_item

    def select_temperature(self) -> None:
        """
        Handles the chat temperature (randomness).
        """
        if self.SHOW_TEMPERATURE_PICKER:
            user_input: str = ""
            lines: int = 1
            while True:
                try:
                    user_input = self.custom_input(f"Press 'ENTER' for the default setting ({self.CHAT_TEMPERATURE}): ")
                    float_temp: float = float(user_input)
                    if 2 >= float_temp >= 0:
                        self.__flush_lines(lines)
                        self.CHAT_TEMPERATURE = float_temp
                        break
                except ValueError:
                    if not user_input:
                        self.__flush_lines(lines)
                        break
                lines += 1

    def roles_chat_menu(self) -> str:
        """
        Handle the roles within the config file.
        If you don't like them, you can create your own.
        """
        if self.SHOW_ROLE_SELECTION:
            roles_names: list[str] = list(self.ALL_ROLES.keys())
            roles_names.remove(self.DEFAULT_ROLE)
            roles_names.append("Add New system behavior")
            selected_role = self.base_chat_menu(
                f'Select a role or use the default one "{self.DEFAULT_ROLE}":',
                "Default",
                roles_names,
                add_nums=False,
                preview_func=self.__role_preview
            )
            if selected_role == "Add New system behavior":
                role: str | None = self.__add_custom_role()
            else:
                role: str | None = self.ALL_ROLES.get(selected_role)
            if not role:
                return self.ALL_ROLES.get(self.DEFAULT_ROLE, "")
            return role
        return self.ALL_ROLES.get(self.DEFAULT_ROLE, "")

    def continue_chat_menu(self) -> list[dict[str, str]] | None:
        """
        Given a Base Path craws a subdir called "chats"
        If there are no files there, it will automatically skip
        the whole function.
        :return: a string which is later handled by continue_chat()
        """
        all_chats: list[str] = os.listdir(self.CHATS_PATH)
        if not len(all_chats):
            return None
        selection: str = self.base_chat_menu("Would you like to continue a previous chat?:", "Skip", all_chats)
        if selection == "Skip":
            return None
        try:
            full_path: str = os.path.join(self.CHATS_PATH, selection)
            with open(full_path, "r") as file:
                data: Any = json.load(file)
                self.custom_print("ok", f"Successfully loaded previous chat - {selection}")
            return data
        except json.JSONDecodeError as e:
            self.custom_print("error", f"Error decoding JSON: {e}", 1)

    def file_prompt(self) -> str | None:
        """
        Opens a custom prompt which supports tab completion.
        If a file is selected that path is being returned.
        If the function is aborted a False is returned.
        """
        try:
            while True:
                user_input = prompt("Enter a path: ", completer=PathCompleter())
                if not os.path.isfile(user_input):
                    self.custom_print("warn", f"No such file at - {user_input}")
                    continue
                with open(user_input, "r") as file:
                    user_prompt: str = file.read()
                    user_prompt.replace("\n", "\\n").replace('"', '\\"')
                    context: str = input(
                        colored(
                            "Add any additional clarification before the submitted text or press 'ENTER' to continue: ",
                            "blue",
                        )
                    )
                    if context:
                        user_prompt = context + ":\n" + user_prompt
                return user_prompt
        except KeyboardInterrupt:
            self.custom_print("info", "Cancelled the file selection, continuing with the chat.")
            return None

    def format_multiline(self):
        """
        Formats a multiline chat input.
        """
        try:
            self.custom_print("info", "Paste the multiline text and press 'Ctrl+D' on an new empty line to continue: ")
            content = sys.stdin.read()
            if content:
                content.replace("\n", "\\n").replace('"', '\\"')
                context = input(
                    colored(
                        "Add additional clarification before the formatted text or press 'ENTER' to continue: ",
                        "blue"))
                if context:
                    content = context + ":\n" + content
            return content
        except KeyboardInterrupt:
            print("\b\b", end="")
            self.custom_print("info", "Cancelled the multiline text, continuing with the chat.")

    def num_tokens_from_messages(self, messages: list[dict]) -> int:
        """
        Count the tokens of the next user prompt
        """
        encoding = tiktoken.encoding_for_model(self.CHAT_MODEL)
        tokens_per_message = 3
        tokens_per_name = 1
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3
        return num_tokens

    def __calculate_costs(self) -> float:
        """
        Calculate the cost of the conversation based on the total prompt tokens and completion tokens.
        :return: total cost of the conversation (float)
        """
        prompt_cost: float = self.conversation_total_prompts_tokens * self.CHAT_MODEL_INPUT_PRICING_PER_1K / 1000
        comp_cost: float = self.conversation_total_completions_tokens * self.CHAT_MODEL_OUTPUT_PRICING_PER_1K / 1000
        return prompt_cost + comp_cost

    def print_costs(self, api_cost: float) -> None:
        """
        Print the cost of the conversation and API usage
        :param api_cost: cost of API usage (float)
        """
        conversation_cost: float = self.__calculate_costs()
        if self.DEBUG:
            self.coloring(
                None,
                "green",
                tokens_used=self.conversation_tokens,
                calculated_prompt_tokens=self.calculated_prompt_tokens,
                prompt_tokens_used=self.conversation_prompt_tokens,
                total_prompt_tokens_used=self.conversation_total_prompts_tokens,
                calculated_completion_max_tokens=self.calculated_completion_max_tokens,
                completion_tokens_used=self.conversation_completion_tokens,
                total_completion_tokens_used=self.conversation_total_completions_tokens,
                chat_cost=locale.currency(conversation_cost, grouping=True),
                api_key_usage_cost=locale.currency(api_cost, grouping=True),
            )
        else:
            self.coloring(
                None,
                "green",
                tokens_used=self.conversation_tokens,
                chat_cost=locale.currency(conversation_cost, grouping=True),
                api_usage_cost=locale.currency(api_cost, grouping=True),
            )

    def update_api_usage(self, usage: float) -> None:
        """
        Update the API usage cost by adding the current conversation cost and a given usage value
        :param usage: additional API usage cost (float)
        """
        api_usage_cost: float = self.__calculate_costs() + usage
        self.write_to_config("chat", "api", "api_usage", new_value=api_usage_cost)

    def flush_chat(self) -> None:
        """
        Reset the conversation and start a new chat.
        """
        self.save_chat(ask=True, skip_exit=True)
        self.base_chat_menu("Would you like to start a new chat?:", "Continue", [])
        self.conversation = [{"role": "system", "content": self.roles_chat_menu()}]
        self.select_temperature()

    def save_chat(self, ask: bool = False, skip_exit: bool = False) -> None:
        """
        Save the current chat to a folder
        :param ask: flag to ask user for confirmation (bool)
        :param skip_exit: flag to skip exit confirmation (bool)
        """
        if ask:
            while True:
                agreement: str = self.custom_input("Would you like to save the chat before you go? y/n: ").lower()
                if agreement == "n" or not agreement:
                    if not skip_exit:
                        self.custom_print("info", "Goodbye! :)", 0)
                    return None
                elif agreement == "y":
                    break
        chat_name: str = self.custom_input("Name the file to save the chat or hit 'Enter' for default name: ")
        if not chat_name:
            base_name: str = "messages"
            timestamp: str = datetime.now().strftime("%Y_%m_%d_%H%M%S")
            file_name: str = f"{base_name}_{timestamp}.json"
        else:
            if not chat_name.endswith(".json"):
                file_name: str = chat_name + ".json"
            else:
                file_name: str = chat_name
        file_path: str = os.path.join(self.CHATS_PATH, file_name)
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(self.conversation, file, indent=4, ensure_ascii=False)
        self.custom_print("ok", f"File saved at - {file_path}")

    def edit_latest(self):
        if not self.conversation or len(self.conversation) < 2:
            self.custom_print("warn", "Seems like your chat has not started yet...")
        else:
            self.save_chat(True, True)
            if self.conversation[-1]["role"] == "assistant":
                self.conversation = self.conversation[:-1]
            self.custom_print(
                "info",
                'This was the last User message in the conversation. You may rewrite it or type a new one instead:')
            print(colored("[User]", self.USER_PROMPT_COLOR) + f" {self.conversation[-1]['content']}")
            self.conversation = self.conversation[:-1]
