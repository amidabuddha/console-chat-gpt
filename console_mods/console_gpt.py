import json
import locale
import os
import sys
from datetime import datetime
import toml
from console_mods.helpers import Helper
import openai
from typing import Any
import readline  # Necessary for input()


class ConsoleGPT(Helper):
    def __init__(self):
        super().__init__()
        self.set_locale()
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

    def main(self) -> None:
        """
        The main function that handles user input, generates AI responses, and manages the conversation flow.
        """
        openai.api_key = self.API_TOKEN
        continue_chat = self.continue_chat_menu()
        if continue_chat:
            self.conversation = continue_chat
        else:
            role: str = self.roles_chat_menu()
            self.conversation = [{"role": "system", "content": role}]
            self.select_temperature()

        while True:
            api_usage_cost: float = toml.load(os.path.join(self.BASE_PATH, "config.toml"))["chat"]["api"]["api_usage"]
            try:
                self.user_input = input(
                    self.coloring(self.USER_PROMPT_COLOR, None, user="", kattrs=["bold", "underline"]))
            except KeyboardInterrupt:
                if self.SAVE_CHAT_ON_EXIT:
                    print()  # since input() does not leave new line on SIGINT
                    self.save_chat(ask=True)
                self.custom_print("error", f"Caught interrupt!", 130)
            match self.user_input.lower():
                case "help" | "commands":
                    self.help_info()
                    continue
                case "cost":
                    self.print_costs(api_usage_cost)
                    continue
                case "file":
                    file_content: str | None = self.file_prompt()
                    if not file_content:
                        continue
                    self.user_input = file_content
                case "flush" | "new":
                    self.flush_chat()
                    continue
                case "format":
                    formatted_input: str | None = self.format_multiline()
                    if not formatted_input:
                        continue
                    self.user_input = formatted_input
                case "save":
                    self.save_chat()
                    continue
                case "exit" | "quit" | "bye":
                    if self.SAVE_CHAT_ON_EXIT:
                        self.save_chat(ask=True)
                    self.custom_print("info", "Bye Bye!", 0)
                case "":
                    self.custom_print("warn", "Don't leave it empty, please :)")
                    continue

            user_message: dict[str, str] = {"role": "user", "content": self.user_input}
            self.conversation.append(user_message)
            calculated_prompt_tokens: int = self.num_tokens_from_messages(self.conversation)
            calculated_completion_max_tokens: int = self.CHAT_MODEL_MAX_TOKENS - calculated_prompt_tokens
            if (calculated_prompt_tokens > self.CHAT_MODEL_MAX_TOKENS) or (
                    calculated_completion_max_tokens < self.LAST_COMPLETION_MAX_TOKENS):
                self.custom_print("error", "Maximum token limit for chat reached")
                self.flush_chat()
                continue
            try:
                response = openai.ChatCompletion.create(
                    model=self.CHAT_MODEL,
                    messages=self.conversation,
                    temperature=self.chat_temperature,
                    max_tokens=calculated_completion_max_tokens,
                )
            except openai.error.OpenAIError as e:  # type: ignore
                self.custom_print("error", f"Unable to generate ChatCompletion:\n {e}")
                self.save_chat(ask=True)
                sys.exit(1)  # adding to avoid warning for response var
            assistant_message: Any = response.choices[0].message  # type: ignore
            assistant_response: dict[str, str] = dict(role="assistant", content=assistant_message["content"])
            self.conversation.append(assistant_response)
            if self.DEBUG:
                with open(os.path.join(self.BASE_PATH, "messages.json"), "w", encoding="utf-8") as log_file:
                    json.dump(self.conversation, log_file, indent=4, ensure_ascii=False)
            print(
                self.coloring(
                    self.ASSISTANT_PROMPT_COLOR,
                    self.ASSISTANT_RESPONSE_COLOR,
                    assistant=self.handle_code_v2(assistant_message["content"]),
                    kattrs=["bold", "underline"],
                )
            )

            self.conversation_tokens += response.usage.total_tokens  # type: ignore
            self.conversation_prompt_tokens = response.usage.prompt_tokens  # type: ignore
            self.conversation_total_prompts_tokens += response.usage.prompt_tokens  # type: ignore
            self.conversation_completion_tokens = response.usage.completion_tokens  # type: ignore
            self.conversation_total_completions_tokens += response.usage.completion_tokens  # type: ignore
            self.update_api_usage(api_usage_cost)
