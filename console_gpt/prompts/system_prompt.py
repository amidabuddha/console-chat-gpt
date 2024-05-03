from rich.console import Console
from rich.markdown import Markdown


def system_reply(data: str, error_msg: str = None) -> None:
    """
    System reply bubble
    :param data: System response
    :return: Nothing, just prints
    """
    if error_msg:
        data = f">{error_msg}\n```{data}```\n"
    console = Console()
    console.print("[green underline bold]╰─❯ System:[/] ")
    markdown = Markdown(data, code_theme="dracula")
    console.print(markdown)
