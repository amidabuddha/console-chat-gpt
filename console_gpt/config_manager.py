import os
from typing import Any, Dict, Iterable, Optional, Union

import toml

from console_gpt.config_struct import CONFIG_STRUCT
from console_gpt.custom_stdout import colored, custom_print


def _join_and_check(*paths, error_message: Optional[str] = None, create: bool = False) -> str:
    """
    Join path presented by `paths` (separate args) and check if exists.
    The path can be created if it doesn't exist and create is enabled
    :param paths: paths to join
    :param error_message: error message to display if path doesn't exist
    :param create: whether to create path if it doesn't exist
    :return: joined path
    """
    q_path = os.path.join(*paths)
    if not os.path.exists(q_path):
        if not create:
            custom_print("error", error_message, 2)
        os.mkdir(q_path)
        custom_print("ok", f"Created the folder - {paths[-1]}")
    return str(q_path)


def _load_toml(conf_path: str) -> Optional[Dict]:
    """
    Load config from file
    :param conf_path: Path to config file
    :return: The data from the config file in dict format
    """
    try:
        return toml.load(conf_path)
    except toml.decoder.TomlDecodeError as e:
        print(e)
        plain_error = str(e).split("(")[-1].replace(")", "")
        colored_error = colored(plain_error, "red")
        custom_print(
            "error",
            f"Empty values and/or duplicates are NOT allowed in the config file [ {colored_error} ]",
            1,
        )


def __structure_scanner(config, expected_structure, parent_key=""):
    warnings = 0
    for key, value in expected_structure.items():
        full_key = f"{parent_key}.{key}" if parent_key else key
        if key not in config:
            custom_print("warn", f"Missing key: {full_key}")
            warnings += 1
        elif isinstance(value, dict):
            warnings += __structure_scanner(config[key], value, parent_key=full_key)
        elif not isinstance(config[key], value):
            custom_print("error", f"Invalid type for {full_key}")
            warnings += 1
    return warnings


def validate_structure():
    status = __structure_scanner(_load_toml(CONFIG_PATH), CONFIG_STRUCT)
    if status == 0:
        custom_print("ok", "Verified and looking fine! You can now proceed with the chat.")
        write_to_config("structure", "valid", new_value=True)
    else:
        write_to_config("structure", "valid", new_value=False)
        # write_to_config("structure", "valid", new_value=False)
        custom_print("info", "Your config file looks wrong, please refer to config.toml.sample", 1)


def __var_error(data: Iterable[Any], auto_exit) -> Union[None, bool]:
    """
    Handled missing/invalid variables within config file
    :param data: the problematic data to handle
    :return: just prints and exits with 1
    """
    data = list(data)
    variable_name = data[-1]
    data.remove(variable_name)
    data = ["chat"] if not len(data) else data
    if auto_exit:
        custom_print(
            "error",
            f"Variable {colored(variable_name, 'red')} is missing under"
            f" {colored('.'.join(data), 'yellow')} in the config.toml!",
            1,
        )
    else:
        return False


BASE_PATH = os.path.dirname(os.path.realpath(f"{__file__}/.."))
CONFIG_PATH = _join_and_check(
    BASE_PATH,
    "config.toml",
    error_message='Please use the "config.toml.sample" to create your configuration.',
)
CONFIG_SAMPLE_PATH = _join_and_check(
    BASE_PATH,
    "config.toml.sample",
    error_message='"config.toml.sample" is either missing or renamed, please udpate from source.',
)
CHATS_PATH = _join_and_check(BASE_PATH, "chats", create=True)
ASSISTANTS_PATH = _join_and_check(BASE_PATH, "assistants", create=True)

def check_valid_config() -> None:
    """
    Checks if the config file structure has been verified after upgrade
    :return: Nothing
    """
    is_checked = fetch_variable("structure", "valid", auto_exit=False)
    if not is_checked:
        custom_print("warn", "It appears that your configuration is not verified. Doing it now...")
        validate_structure()


def fetch_version() -> str:
    """
    Fetch version from the config sample file (config.toml.sample)
    :return: config current version as string
    """
    config = _load_toml(CONFIG_SAMPLE_PATH)
    return config["chat"]["structure"]["version"]


def check_config_version() -> None:
    """
    Checks if the config file has the current version even if the content seems valid
    :return: Nothing
    """
    config_version = fetch_variable("structure", "version", auto_exit=False)
    sample_config_version = fetch_version()
    if config_version != sample_config_version:
        write_to_config("structure", "valid", new_value=False)
        custom_print("warn", "It appears that your configuration is not up-to-date.")
        custom_print("info", 'Please use the contents of "config.toml.sample" to update your configuration.', 0)


def write_to_config(*args, new_value: Any, group: bool = False) -> None:
    """
    Writes a new value to the config file
    :param args: The keys to access the value in the config file
    :param new_value: The new value to be written
    :param group: Allow creating groups
    """
    config = _load_toml(CONFIG_PATH)
    if group:
        config["chat"][args[0]] = {args[1]: new_value}
    match len(args):
        case 1:
            config["chat"][args[0]] = new_value
        case 2:
            config["chat"][args[0]][args[1]] = new_value
        case 3:
            config["chat"][args[0]][args[1]][args[2]] = new_value
        case 4:
            config["chat"][args[0]][args[1]][args[2]][args[3]] = new_value
        case _:
            custom_print("error", "Wrong usage of write_to_config", 1)

    with open(CONFIG_PATH, "w") as file:
        toml.dump(config, file)


def fetch_variable(*args, auto_exit: bool = True) -> Any:
    """
    Fetch variable from the config file (config.toml)
    By default the function is already looking into the "chat" group
    :param args: variable group/name as deep as necessary
    :param auto_exit: Automatically abort if var is missing
    :return: Content or Error (with exit)
    """
    config = _load_toml(CONFIG_PATH)
    chat_var = config["chat"]
    try:
        match len(args):
            case 1:
                return chat_var[args[0]]
            case 2:
                return chat_var[args[0]][args[1]]
            case 3:
                return chat_var[args[0]][args[1]][args[2]]
            case _:
                custom_print(
                    "error",
                    f"You're asking for variable that does NOT exist! " f"- {colored('.'.join(args), 'red')}",
                    1,
                )

    except KeyError:
        return __var_error(args, auto_exit)
