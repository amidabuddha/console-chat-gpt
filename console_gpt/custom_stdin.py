import shutil
from math import ceil

from questionary import text

from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines


def _calculate_num_of_lines(input_text: str) -> int:
    """
    Calculates the number of lines utilized by the question + user input
    The line number is based on the terminal size
    :param input_text:
    :return: number of lines
    """
    columns, _ = shutil.get_terminal_size()
    number_of_lines = ceil((len(input_text) + 4) / columns)
    return number_of_lines


def custom_input(
    is_single_line: bool = True, auto_exit: bool = True, exit_message: str = "Goodbye! See you later!", **default_args
):
    """
    Custom function for STDIN which flushes lines to keep everything clean
    :param is_single_line: Whether the question is single line
    :param auto_exit: Exit automatically if user input is None (SIGINT usually)
    :param exit_message: Custom exit message
    :param default_args: The default arguments supported by questionary.text()
    :return: the content
    """
    user_input = text(**default_args).ask()
    if user_input is None:
        to_remove = sum([_calculate_num_of_lines(x) for x in default_args["message"].split("\n")])
        flush_lines(to_remove - (1 if is_single_line else 0) + 4)
        if auto_exit:
            custom_print("exit", exit_message, 130)
        return None
    to_remove = sum([_calculate_num_of_lines(x) for x in user_input.split("\n") + default_args["message"].split("\n")])
    flush_lines(to_remove - (1 if is_single_line else 0))
    return user_input
