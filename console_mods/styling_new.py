from typing import List, Optional, Union

from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound
from termcolor import colored


def custom_print(
    ptype: str, text: str, exit_code: Optional[int] = -1, print_now: Optional[bool] = True
) -> Union[None, str]:
    match ptype:
        case "ok":
            formatted_text: str = colored("[OK] ", "green") + text
        case "warn":
            formatted_text: str = colored("[WARN] ", "yellow") + text
        case "info":
            formatted_text: str = colored("[INFO] ", "blue") + text
        case "error":
            formatted_text: str = colored("[ERROR] ", "red") + text
        case _:
            formatted_text: str = colored("[ERROR] ", "Wrong usage of custom_print!")

    if exit_code != -1:
        print(formatted_text)
        exit(exit_code)

    return formatted_text if not print_now else print(formatted_text)


def kwargs_coloring(*color, **data) -> None:
    for key, value in data.items():
        key = " ".join(key.split("_")) if key.count("_") else key
        print(f"{colored(key.title(), color[0])}: {colored(value, color[1])}")


def _code_coloring(code, lang):
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    formatter = TerminalFormatter()
    highlighted_code = highlight(code, lexer, formatter)
    print(highlighted_code)


def handle_code(text: str, content_color: str) -> None:
    current_lang: str = "text"
    current_code: List[Optional[str]] = []
    in_code_block: bool = False

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if in_code_block:
                code: str = "\n".join(current_code)
                if not current_lang:
                    print(colored(code, color=content_color))
                else:
                    _code_coloring(code, current_lang)
                current_code = []
                in_code_block = False
            else:
                current_lang = line.lstrip()[3:].strip() or "text"
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
            _code_coloring(code, current_lang)
