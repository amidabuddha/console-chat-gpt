from sys import exit
from typing import List, Any

from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_by_name
from termcolor import colored


class Prettify:
    @staticmethod
    def custom_print(
            ptype: str,
            text: str,
            exit_code: int = -1,
            print_now: bool = True,
    ) -> None | str:
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
        kattrs: List[str] | None = data.pop("kattrs", None)  # Key attributes
        vattrs: List[str] | None = data.pop("vattrs", None)  # Value attributes
        for key, value in data.items():
            key: str = " ".join(key.split("_")) if key.count("_") else key
            if len(data.keys()) == 1:
                return f"{colored(key.capitalize(), color[0], attrs=kattrs)}: {colored(value, color[1], attrs=vattrs)}"
            print(f"{colored(key.capitalize(), color[0], attrs=kattrs)}: {colored(value, color[1], attrs=vattrs)}")

    @staticmethod
    def code_coloring(code, lang):
        lexer = get_lexer_by_name(lang)
        formatter = TerminalFormatter()
        highlighted_code = highlight(code, lexer, formatter)
        print(highlighted_code)

    def handle_code(self, text: str, content_color: str) -> None:
        """
        Handles code inside the Assistance response by matching the
        standard Markdown syntax for code block no matter space (\\s) or tab(\\t)
        at the beginning
        """
        current_lang: str = "text"
        current_code: List[Any] = []
        in_code_block: bool = False

        for line in text.splitlines():
            if line.startswith("```"):
                if in_code_block:
                    code: str = "\n".join(current_code)
                    if not current_lang:
                        print(colored(code, color=content_color))
                    else:
                        self.code_coloring(code, current_lang)
                    current_code = []
                    in_code_block = False
                else:
                    current_lang = line[3:].strip() or "text"
                    in_code_block = True
            elif in_code_block:
                current_code.append(line)
            else:
                print(colored(line, color=content_color))

        if in_code_block:
            code = "\n".join(current_code)
            if not current_lang:
                print(colored(code, color=content_color))
            else:
                self.code_coloring(code, current_lang)
