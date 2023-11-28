import shutil
from math import ceil

from questionary import text

from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import flush_lines


def _calculate_num_of_lines(input_text: str) -> int:
    columns, _ = shutil.get_terminal_size()
    number_of_lines = ceil((len(input_text) + 4) / columns)
    return number_of_lines


def custom_input(
    is_single_line: bool = True, exit_message: str = "Goodbye! See you later!", **default_args
):
    user_input = text(**default_args).ask()
    if user_input is None:
        to_remove = sum([_calculate_num_of_lines(x) for x in default_args["message"].split("\n")])
        flush_lines(to_remove - (1 if is_single_line else 0) + 4)
        custom_print("exit", exit_message, 130)
    to_remove = sum(
        [
            _calculate_num_of_lines(x)
            for x in user_input.split("\n") + default_args["message"].split("\n")
        ]
    )
    flush_lines(to_remove - (1 if is_single_line else 0))
    return user_input
