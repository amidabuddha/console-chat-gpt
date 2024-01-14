import locale
import os
import platform
from typing import Optional, TypeVar

from rich.console import Console
from rich.table import Table

from console_gpt.changelog_manager import get_changelog
from console_gpt.config_manager import fetch_variable, write_to_config
from console_gpt.custom_stdout import custom_print

# Used to Hint that the expected input is a single char and not a string.
Char = TypeVar("Char", bound=str)


def use_emoji_maybe(emoji: str, fallback: Optional[Char] = None) -> str:
    """
    Return emoji if the OS supports it and if it's enabled in the settings
    :param emoji: Unicode for the emoji
    :param fallback: The fallback char/word (ASCII) to be displayed if emoji is not supported
    :return: either emoji or the fallback char/word
    """
    use_emoji = fetch_variable("customizations", "use_emoji")
    fallback_char = fetch_variable("customizations", "fallback_char")[0]
    fallback_char = fallback_char if not fallback else fallback[0]

    # if emoji is disabled return a question mark (default by the library anyway)
    if not use_emoji:
        return fallback_char

    # Check the platform type
    plt = platform.system().lower()
    support = False
    if plt in ["windows", "darwin"]:  # macOS is 'darwin'
        support = True

    # For Linux/Unix, we might check the environment for a known terminal that supports emojis.
    term = os.getenv("TERM")
    if term and "xterm" in term:
        support = True

    return emoji if support else fallback_char


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


def help_message() -> None:
    """
    Print the supported commands
    :return: None, just prints
    """
    console = Console()

    table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
    table.add_column(justify="right")
    table.add_column(justify="left")

    options = {
        "help": "Prints all available commands.",
        "cost": "Prints the costs of the current chat.",
        "edit": "Prints the last prompt so you can edit it.",
        "exit": "Exits the chat.",
        "file": "Allows you to upload a file to the chat.",
        "image": "Allows you to upload an image [Supported by gpt-4-vision-preview only].",
        "flush": "Start the chat all over again.",
        "format": "Allows you to write multiline messages.",
        "save": "Saves the chat to a given file.",
        "settings": "Manage available features.",
    }

    for option, description in options.items():
        table.add_row(f"[bold]{option}[/bold]:", description, style="green")

    console.print(table)


def intro_message() -> None:
    """
    Print once the supported commands upon very first run of the application
    :return: None, just prints
    """
    get_changelog()
    if not fetch_variable("features", "disable_intro_help_message"):
        help_message()


def capitalize(string) -> str:
    """
    Takes snake_case strings as input and transforms into capitalized words, separated by space symbol.
    :return: Modified string
    """
    return string.replace("_", " ").title()


def decapitalize(string) -> str:
    """
    Takes capitalized words, separated by space symbol as input and transforms into snake_case strings.
    :return: Modified string
    """
    return string.replace(" ", "_").lower()
