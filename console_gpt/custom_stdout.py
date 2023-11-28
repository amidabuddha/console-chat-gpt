from typing import Literal, Optional

from termcolor import colored

# Define the specific types for 'ptype'
PrintType = Literal["ok", "warn", "info", "error", "sigint", "exit"]


def custom_print(
    ptype: PrintType,
    text: str,
    exit_code: Optional[int] = None,
    print_now: Optional[bool] = True,
    start: Optional[str] = "",
    end: Optional[str] = "",
) -> Optional[str]:
    """
    Based on the ptype (Print Type) it will print messages in different color.
    If print_now is set to False it will return the colored string.
    If exit_code is set to a value different from -1 the function
    will exit the whole program.
    """
    formats = {
        "ok": ("[OK] ", "green"),
        "warn": ("[WARN] ", "yellow"),
        "info": ("[INFO] ", "blue"),
        "error": ("[ERROR] ", "red"),
        "sigint": ("[SIGINT] ", "red"),
        "exit": ("[EXIT] ", "red"),
    }

    prefix, color = formats.get(ptype.lower(), ("[UNKNOWN] ", "white"))
    formatted_text = start + colored(prefix, color) + text + end

    if print_now:
        print(formatted_text)
        if exit_code is not None:
            exit(exit_code)
    else:
        if exit_code is not None:
            print(f"Cannot use exit_code when not printing immediately.")
            exit(1)

    return formatted_text if not print_now else None
