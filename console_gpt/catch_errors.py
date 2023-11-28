from console_gpt.custom_stdout import custom_print


def eof_wrapper(func):
    """
    Decorator to wrap EOFError exception from a function and allow
    the user to attempt to continue
    :param func: function to wrap
    :return: wrapped function or exit
    """

    def inner(*args, **kwargs):
        retries = 3  # Set a limit for retries
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except EOFError:
                custom_print(
                    "warn",
                    "Caught irregular interrupt (EOF). Please stick to the menus or SIGINT! ({retries})",
                )
                retries -= 1  # Decrement the retry counter
        custom_print("error", "Maximum retries exceeded. Exiting function.", 1)

    return inner
