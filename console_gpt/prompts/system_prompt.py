from rich.console import Console
from rich.markdown import Markdown


def system_reply(data: str) -> None:
    """
    System reply bubble
    :param data: System response
    :return: Nothing, just prints
    """
    console = Console()
    console.print("[green underline bold]╰─❯ System:[/] ")
    markdown = Markdown(data, code_theme="dracula")
    console.print(markdown)
