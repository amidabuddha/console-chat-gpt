from termcolor import colored
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_by_name
import re
from typing import AnyStr
from sys import exit


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
            print(formatted_text)
            exit(exit_code)

        return formatted_text if not print_now else print(formatted_text)

    def custom_input(self, prompt_text: str) -> str:
        return input(self.custom_print("info", colored(prompt_text, "yellow"), print_now=False))

    @staticmethod
    def coloring(*color, **data) -> str | None:
        """
        Accept colors as *args (*colors) - max 2
        Accepts str as **kwargs (**data)
        Maps colors with key:value:
        0 -> Key
        1 -> Value
        """
        kattrs: list[str] | None = data.pop("kattrs", None)  # Key attributes
        vattrs: list[str] | None = data.pop("vattrs", None)  # Value attributes
        for key, value in data.items():
            key: str = " ".join(key.split("_")) if key.count("_") else key
            if len(data.keys()) == 1:
                return f"{colored(key.capitalize(), color[0], attrs=kattrs)}: {colored(value, color[1], attrs=vattrs)}"
            print(f"{colored(key.capitalize(), color[0], attrs=kattrs)}: {colored(value, color[1], attrs=vattrs)}")

    @staticmethod
    def handle_code_v2(text: str) -> str:
        """
        Handles code inside the Assistance response by matching the
        standard Markdown syntax for code block no matter space (\\s) or tab(\\t)
        at the beginning
        """
        result: list = []
        code_regex: re.Pattern[str] = re.compile(r"^(`{3}|(\t|\s)+`{3})")
        catch_code_regex: str = r"```.*?```"
        clear_code_regex: str = r"```(.*)?"
        matches = re.search(clear_code_regex, text)
        language: str = "python"
        if matches:
            try:
                language = [x for x in matches.groups() if x and x != "plaintext"][0]
            except (IndexError, AttributeError):
                language = "python"

        formatter = TerminalFormatter()
        catch_code: list[str] = re.findall(catch_code_regex, text, re.DOTALL)
        clear_code: list[str] = [re.sub(clear_code_regex, "", x) for x in catch_code]
        highlighted_code: list = [highlight(x, get_lexer_by_name(language), formatter) for x in clear_code]
        total_code: int = len(highlighted_code)
        counter: int = 0
        words: list[str] = text.split("\n")
        skip_add: bool = False
        is_code: bool = False
        for word in words:
            if code_regex.search(word):
                skip_add = True if not skip_add else False
                is_code = True
                continue
            if skip_add:
                continue
            if not skip_add and is_code:
                if counter <= total_code:
                    result.append(highlighted_code[counter])
                is_code = False
                counter += 1
                continue

            if not skip_add and not is_code:
                from console_mods.config_attrs import FetchConfig
                result.append(colored(word, FetchConfig().ASSISTANT_RESPONSE_COLOR))
        return "\n".join([x for x in result if x])
