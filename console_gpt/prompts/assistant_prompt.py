from rich.console import Console
from rich.markdown import Markdown


def assistance_reply(data: str) -> None:
    console = Console()
    console.print("[blue underline bold]╰─❯ Assistant:[/] ", end="")
    # console.print("[blue underline bold]{} Assistant:[/] ".format(use_emoji_maybe("\U0001F916")), end="")
    markdown = Markdown(data, code_theme="dracula")
    console.print(markdown)
