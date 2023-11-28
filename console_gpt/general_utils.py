import locale
import os
import platform
import sys
from typing import Optional

from termcolor import colored

from console_gpt.custom_stdout import custom_print


def use_emoji_maybe(emoji: str, fallback: str = "?") -> str:
    # Check the platform type
    plt = platform.system().lower()
    support = False
    if plt in ["windows", "darwin"]:  # macOS is 'darwin'
        support = True

    # For Linux/Unix, we might check the environment for a known terminal that supports emojis.
    term = os.getenv("TERM")
    if term and "xterm" in term:
        support = True

    # If running in Jupyter notebooks or similar environments, they typically support emojis.
    if "ipykernel" in sys.modules or "IPython" in sys.modules:
        support = True

    return emoji if support else colored(fallback, "blue")


def flush_lines(lines: Optional[int] = 1) -> None:
    """
    Flushes the given number of lines on the console
    :param lines: The number of lines to flush.
    """
    print("\033[F\033[K" * lines, end="")


def set_locale() -> None:
    """
    Sets the locale based on the operating system.
    """
    match platform.system():
        case "Darwin":
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        case "Linux":
            locale.setlocale(locale.LC_ALL, "en_US.utf8")
        case _:
            custom_print("warn", f"Unable to detect OS. Setting a default locale.")
            locale.setlocale(locale.LC_ALL, "")
