import sys

from termcolor import colored


def coloring(*colors, **data) -> (str, None):
    kattrs = data.pop("kattrs", None)  # Key attributes
    vattrs = data.pop("vattrs", None)  # Value attributes

    for key, value in data.items():
        key = " ".join(key.split("_")) if key.count("_") else key
        if len(data.keys()) == 1:
            return f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        print(
            f"{colored(key.capitalize(), colors[0], attrs=kattrs)}: {colored(value, colors[1], attrs=vattrs)}"
        )


def code_coloring(text: str, color: str, on_color: bool = False, skip=False):
    if on_color and not skip:
        return colored(text, color)
    if skip:
        return ""
    from chat import ASSISTANT_RESPONSE_COLOR

    return colored(text, ASSISTANT_RESPONSE_COLOR)


def handle_code(text: str, code_color: str) -> str:
    result = []
    words = text.split("\n")
    enable_color = False
    skip_add = False
    for word in words:
        if word.startswith("```"):
            enable_color = True if not enable_color else False
            skip_add = True if not skip_add else False
        result.append(code_coloring(word, code_color, enable_color, skip_add))
        skip_add = False
    return "\n".join([x for x in result if x])


def error_msg(text: str) -> None:
    print(colored(f"[ERROR] {text}", "red"))
    sys.exit(1)


def info_msg(text: str) -> str:
    return colored(text, "blue")
