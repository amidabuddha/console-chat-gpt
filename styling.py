import sys
from termcolor import colored
import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter


def coloring(*colors, **data) -> (str, None):
    """
    Accept colors as *args (*colors) - max 2
    Accepts str as **kwargs (**data)
    Maps colors with key:value:
    0 -> Key
    1 -> Value
    """
    kattrs = data.pop("kattrs", None)  # Key attributes
    vattrs = data.pop("vattrs", None)  # Value attributes

    for key, value in data.items():
        key = " ".join(key.split("_")) if key.count("_") else key
        if len(data.keys()) == 1:
            return f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        print(f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}")


def code_coloring(text: str, color: str, on_color: bool = False, skip: bool = False) -> str:
    """
    Custom function for `handle_code`
    It allows skipping entries and coloring based on the type
    Either code or response by the Assistant (chat).
    """
    if on_color and not skip:
        return colored(text, color)
    if skip:
        return ""
    from chat import ASSISTANT_RESPONSE_COLOR
    return colored(text, ASSISTANT_RESPONSE_COLOR)


def handle_code_v2(text: str, code_color: str) -> str:
    """
    Handles code inside the Assistance response by matching the
    standard Markdown syntax for code block no matter space (\s) or tab(\\t)
    at the beginning
    """
    result = []
    code_regex = re.compile("^(`{3}|(\t|\s)+`{3})")
    catch_code_regex = r'```.*?```'
    clear_code_regex = r'```(.*)?'
    try:
        language = [x for x in re.search(clear_code_regex, text).groups() if x and x != "plaintext"][0]
    except (IndexError, AttributeError):
        language = "python"

    formatter = TerminalFormatter()
    catch_code = re.findall(catch_code_regex, text, re.DOTALL)
    clear_code = [re.sub(clear_code_regex, '', x) for x in catch_code]
    highlighted_code = [highlight(x, get_lexer_by_name(language), formatter) for x in clear_code]
    total_code = len(highlighted_code)
    counter = 0
    words = text.split("\n")
    skip_add = False
    is_code = False
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
            from chat import ASSISTANT_RESPONSE_COLOR
            result.append(colored(word, ASSISTANT_RESPONSE_COLOR))
    return "\n".join([x for x in result if x])


def handle_code(text: str, code_color: str) -> str:
    """
    Handles code inside the Assistance response by matching the
    standard Markdown syntax for code block no matter space (\s) or tab(\\t)
    at the beginning
    """
    code_regex = re.compile("^(`{3}|(\t|\s)+`{3})")
    result = []
    words = text.split("\n")
    enable_color = False
    skip_add = False
    for word in words:
        if code_regex.search(word):
            enable_color = True if not enable_color else False
            skip_add = True if not skip_add else False
        result.append(code_coloring(word, code_color, enable_color, skip_add))
        skip_add = False
    return "\n".join([x for x in result if x])


def custom_print(ptype: str, text: str, exit_code: int = -1, print_now: bool = True, ) -> (None, str):
    """
    Based on the ptype (Print Type) it will print messages in different color.
    If print_now is set to False it will return the colored string.
    If exit_code is set to a value different from -1 the function
    will exit the whole program.
    """
    match ptype:
        case "ok":
            formatted_text = colored("[OK] ", "green") + text
            if not print_now:
                return formatted_text
            print(formatted_text)
        case "warn":
            formatted_text = colored("[WARN] ", "yellow") + text
            if not print_now:
                return formatted_text
            print(formatted_text)
        case "info":
            formatted_text = colored("[INFO] ", "blue") + text
            if not print_now:
                return formatted_text
            print(formatted_text)
        case "error":
            formatted_text = colored("\n[ERROR] ", "red") + text
            if not print_now:
                return formatted_text
            print(formatted_text)

    if exit_code != -1:
        sys.exit(exit_code)
