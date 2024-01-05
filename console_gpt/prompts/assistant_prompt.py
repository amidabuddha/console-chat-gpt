from console_gpt.custom_stdout import markdown_print


def assistance_reply(data: str) -> None:
    """
    GPT reply bubble
    :param data: GPT response
    :return: Nothing, just prints
    """
    markdown_print(data, "Assistant", end="\n")
