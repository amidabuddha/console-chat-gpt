from rich.console import Console
from rich.markdown import Markdown


def assistance_reply(data: str) -> None:
    console = Console()
    console.print("[blue underline bold]╰─❯ Assistant:[/] ")
    markdown = Markdown(data, code_theme="dracula")
    console.print(markdown)
