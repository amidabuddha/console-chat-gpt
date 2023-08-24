from console_mods.styling import Prettify, colored
import os
import toml
from typing import Any


class FetchConfig(Prettify):
    def __init__(self):
        self.BASE_PATH: str = os.path.dirname(os.path.realpath(f"{__file__}/.."))
        self.CONFIG_PATH: str = self.__path_exist(
            os.path.join(self.BASE_PATH, "config.toml"),
            'Please use the "config.toml.sample" to create your configuration.',
        )
        self.CHATS_PATH: str = self.__path_exist(os.path.join(self.BASE_PATH, "chats"), create=True)

        try:
            self.config: dict[str, Any] = toml.load(self.CONFIG_PATH)
        except toml.decoder.TomlDecodeError as e:
            error: str = colored(str(e).split("(")[1].replace(")", ""), "red", attrs=["bold", "underline"])
            self.custom_print("error", f"Empty values are NOT allowed in the config file!: {error}", 1)

        self.ALL_ROLES: dict[str, str] = self.fetch_variable("chat", "roles")
        self.DEFAULT_ROLE: str = self.fetch_variable("chat", "default_system_role")
        self.DEBUG: bool = self.fetch_variable("chat", "debug")
        self.SHOW_ROLE_SELECTION: bool = self.fetch_variable("chat", "role_selector")
        self.SHOW_TEMPERATURE_PICKER: bool = self.fetch_variable("chat", "adjust_temperature")
        self.SAVE_CHAT_ON_EXIT: bool = self.fetch_variable("chat", "save_chat_on_exit")
        self.LAST_COMPLETION_MAX_TOKENS: int = self.fetch_variable("chat", "last_completion_max_tokens")

        # Color settings
        self.USER_PROMPT_COLOR: str = self.fetch_variable("chat", "colors", "user_prompt")
        self.ASSISTANT_PROMPT_COLOR: str = self.fetch_variable("chat", "colors", "assistant_prompt")
        self.ASSISTANT_RESPONSE_COLOR: str = self.fetch_variable("chat", "colors", "assistant_response")

        # API settings
        self.API_TOKEN: str = self.__fetch_api_token(self.fetch_variable("chat", "api", "api_key"))
        self.CHAT_MODEL: str = self.fetch_variable("chat", "model", "model_name")
        self.CHAT_TEMPERATURE: float = float(self.fetch_variable("chat", "temperature"))
        self.CHAT_MODEL_INPUT_PRICING_PER_1K: float = self.fetch_variable("chat", "model", "model_input_pricing_per_1k")
        self.CHAT_MODEL_OUTPUT_PRICING_PER_1K: float = self.fetch_variable(
            "chat", "model", "model_output_pricing_per_1k"
        )
        self.CHAT_MODEL_MAX_TOKENS: int = self.fetch_variable("chat", "model", "model_max_tokens")

        # Chat-related variables
        self.user_input: str = ""
        self.conversation: list[dict[str, str]] = []
        self.chat_temperature: float = self.CHAT_TEMPERATURE
        self.conversation_tokens: int = 0
        self.conversation_prompt_tokens: int = 0
        self.conversation_total_prompts_tokens: int = 0
        self.conversation_completion_tokens: int = 0
        self.conversation_total_completions_tokens: int = 0
        self.calculated_prompt_tokens: int = 0
        self.calculated_completion_max_tokens: int = self.CHAT_MODEL_MAX_TOKENS

    def __path_exist(self, dest_path: str, error_message: str = "", create: bool = False) -> str:
        """
        Checks if a particular path (file; folder) exists
        :param dest_path: The file/folder to check
        :param error_message: Error message that will be returned if it doesn't exist (exits with 2)
        :param create: If the folder does not exist - creates it and doesn't exit
        :return: The destination folder
        """
        if not os.path.exists(dest_path):
            if not create:
                self.custom_print("error", error_message, 2)
            os.mkdir(dest_path)
            self.custom_print("ok", f"Created the folder - {dest_path}")
        return dest_path

    def __fetch_api_token(self, token: str) -> str:
        """
        Checks if the API Token has been included inside the config file
        :param token: The API token so it can check if it is empty
        :return: The API token.
        """
        if not token:
            self.custom_print("error", f"Please make sure that the API token is inside {self.CONFIG_PATH}", 1)
        return token

    def __var_error(self, data: tuple[Any, ...]):
        data = list(data)
        variable_name = data[-1]
        data.remove(variable_name)
        self.custom_print(
            "error",
            f"Variable {colored(variable_name, 'red')} is missing under"
            f" {colored('.'.join(data), 'yellow')} in the config.toml!",
            1,
        )

    def fetch_variable(self, *args) -> Any | None:
        match len(args):
            case 2:
                try:
                    return self.config[args[0]][args[1]]
                except KeyError:
                    self.__var_error(args)
            case 3:
                try:
                    return self.config[args[0]][args[1]][args[2]]
                except KeyError:
                    self.__var_error(args)
            case _:
                print("Unknown")
