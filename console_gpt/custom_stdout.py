from typing import Literal, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
from termcolor import colored

# Define the specific types for 'ptype'
PrintType = Literal["ok", "warn", "info", "error", "sigint", "exit", "changelog"]


def markdown_print(data: str, header: Optional[str] = None, end: Optional[str] = ""):
    console = Console()

    # Print the header if it exists
    if header:
        header_text = Text(f"╰─❯ {header}:", style="blue underline bold")
        console.print(header_text, end=end)

    # Create a Markdown object
    markdown = Markdown(data, code_theme="dracula")

    # Print the Markdown content with word wrapping handled by Console
    console.print(markdown, width=console.width)


def markdown_stream(chunks):
    console = Console()
    response = ""
    with Live(console=console, refresh_per_second=10, vertical_overflow="ellipsis") as live:
        for chunk in chunks:
            response += chunk
            md = Markdown(response, code_theme="dracula")
            live.update(md)
    return response


def custom_print(
    ptype: PrintType,
    text: str,
    exit_code: Optional[int] = None,
    print_now: Optional[bool] = True,
    start: Optional[str] = "",
    end: Optional[str] = "",
) -> Optional[str]:
    """
    Custom STDOUT function which works soft of like logging
    It uses pre-defined prefixes (E.g. `[ERROR] <your_text>`)
    :param ptype: Print type (the mentioned prefix)
    :param text: the text you would like to print
    :param exit_code: custom exit status if you like to abort everything
    :param print_now: whether to print or return the content
    :param start: Add custom text before the prefix
    :param end: Add custom text after the text
    :return: The content if "print_now" is false
    """

    formats = {
        "ok": ("[OK] ", "green"),
        "warn": ("[WARN] ", "yellow"),
        "info": ("[INFO] ", "blue"),
        "error": ("[ERROR] ", "red"),
        "sigint": ("[SIGINT] ", "red"),
        "exit": ("[EXIT] ", "red"),
        "changelog": ("[CHANGELOG] ", "cyan"),
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
