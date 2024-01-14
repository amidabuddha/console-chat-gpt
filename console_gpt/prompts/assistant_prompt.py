from console_gpt.custom_stdout import markdown_print


def assistance_reply(data: str, title="Assistant") -> None:
    """
    GPT reply bubble
    :param data: GPT response
    :return: Nothing, just prints
    """
    markdown_print(data, title, end="\n")
