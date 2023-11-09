import json
import os
import readline  # Necessary for input()
import sys
from typing import Any, List

import openai
import toml
from colorama import Style
from halo import Halo
from termcolor import colored, cprint

from console_mods.helpers import Helper


class ConsoleGPT(Helper):
    def __init__(self):
        super().__init__()
        self.set_locale()
        self.spinner = Halo(text="Generating Output", spinner="dots")

    def main(self) -> None:
        """
        The main function that handles user input, generates AI responses, and manages the conversation flow.
        """
        self.select_model_menu()
        openai.api_key = self.API_TOKEN
        continue_chat: List[dict[str, str]] | None = self.continue_chat_menu()
        if continue_chat:
            self.conversation = continue_chat
        else:
            role: str = self.roles_chat_menu()
            self.conversation = [{"role": "system", "content": role}]
            self.select_temperature()

        while True:
            api_usage_cost: float = toml.load(os.path.join(self.BASE_PATH, "config.toml"))["chat"]["models"][
                self.SELECTED_MODEL
            ]["api_usage"]
            try:
                cprint("User: ", self.USER_PROMPT_COLOR, end="", attrs=["bold", "underline"])
                self.user_input = input(f"\b {Style.RESET_ALL}")
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
                case "edit":
                    self.edit_latest()
                    continue
                case "exit" | "quit" | "bye":
                    if self.SAVE_CHAT_ON_EXIT:
                        self.save_chat(ask=True)
                    self.custom_print("info", "Bye Bye!", 0)
                case "":
                    self.custom_print("warn", "Don't leave it empty, please :)")
                    continue
            self.spinner.start()
            user_message: dict[str, str] = {"role": "user", "content": self.user_input}
            self.conversation.append(user_message)
            # calculated_prompt_tokens: int = self.num_tokens_from_messages(self.conversation)
            # calculated_completion_max_tokens: int = self.CHAT_MODEL_MAX_TOKENS - calculated_prompt_tokens
            calculated_completion_max_tokens: int = self.CHAT_MODEL_MAX_TOKENS
            # if (calculated_prompt_tokens > self.CHAT_MODEL_MAX_TOKENS) or (
            #     calculated_completion_max_tokens < self.LAST_COMPLETION_MAX_TOKENS
            # ):
            #     self.custom_print("error", "Maximum token limit for chat reached")
            #     self.spinner.stop()
            #     self.flush_chat()
            #     continue
            try:
                response = openai.ChatCompletion.create(
                    model=self.CHAT_MODEL,
                    messages=self.conversation,
                    temperature=self.chat_temperature,
                    max_tokens=calculated_completion_max_tokens,
                )
            except openai.error.OpenAIError as e:  # type: ignore
                self.custom_print("error", f"Unable to generate ChatCompletion:\n {e}")
                self.spinner.stop()
                self.save_chat(ask=True)
                sys.exit(1)  # adding to avoid warning for response var
            assistant_message: Any = response.choices[0].message  # type: ignore
            assistant_response: dict[str, str] = dict(role="assistant", content=assistant_message["content"])
            self.conversation.append(assistant_response)
            if self.DEBUG:
                with open(os.path.join(self.BASE_PATH, "messages.json"), "w", encoding="utf-8") as log_file:
                    json.dump(self.conversation, log_file, indent=4, ensure_ascii=False)
            self.spinner.stop()
            cprint("Assistant:", self.ASSISTANT_PROMPT_COLOR, end=" ", attrs=["bold", "underline"])
            self.handle_code(assistant_message["content"], self.ASSISTANT_RESPONSE_COLOR)
            self.conversation_tokens += response.usage.total_tokens  # type: ignore
            self.conversation_prompt_tokens = response.usage.prompt_tokens  # type: ignore
            self.conversation_total_prompts_tokens += response.usage.prompt_tokens  # type: ignore
            self.conversation_completion_tokens = response.usage.completion_tokens  # type: ignore
            self.conversation_total_completions_tokens += response.usage.completion_tokens  # type: ignore
            self.update_api_usage(api_usage_cost)
