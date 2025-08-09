import os
import shutil
from typing import Any, Dict, Iterable, List, Literal, Optional, Union

import toml

from console_gpt.custom_stdout import colored, custom_print

# Define the specific types for 'create' for join_and_check function
CreateType = Literal["folder", "config.toml", "mcp_config.json"]


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


def _prune_models(conf_path: str) -> None:
    """Trim models in a freshly created config.toml to only the ones referenced elsewhere.

    Keeps:
      - defaults.model
      - managed.assistant
      - managed.assistant_{generalist,fast,thinker,coder}
    The large master list remains in config.toml.sample and can still be used via the
    model add menu. This keeps the initial user config concise.
    """
    config = _load_toml(conf_path)
    if not config or "chat" not in config or "models" not in config["chat"]:
        return
    chat = config["chat"]
    models = chat.get("models", {})
    managed = chat.get("managed", {})
    defaults = chat.get("defaults", {})

    required_keys = set()
    # defaults
    default_model = defaults.get("model")
    if isinstance(default_model, str):
        required_keys.add(default_model)
    # managed variants
    for k in ("assistant", "assistant_generalist", "assistant_fast", "assistant_thinker", "assistant_coder"):
        val = managed.get(k)
        if isinstance(val, str):
            required_keys.add(val)

    # Safety: if required set empty or any key missing from models skip pruning
    if not required_keys:
        return
    existing_required = [k for k in models.keys() if k in required_keys]
    if not existing_required:
        return
    # If nothing to prune (already minimal) skip
    if len(existing_required) == len(models):
        return
    # Preserve original order
    pruned_models = {k: models[k] for k in models if k in required_keys}
    if pruned_models:
        chat["models"] = pruned_models
        with open(conf_path, "w") as f:
            toml.dump(config, f)
        custom_print("ok", f"Trimmed models list to required model(s): {', '.join(pruned_models.keys())}")


def _join_and_check(*paths, create: Optional[CreateType] = None, target: Optional[CreateType] = None) -> str:
    """
    Join path presented by `paths` (separate args) and check if exists.
    The path can be created if it doesn't exist and create is enabled
    :param paths: paths to join
    :param create: whether to create path if it doesn't exist
    :param target: the file that would be created if this path exist (for sample files)
    :return: joined path
    """
    q_path = os.path.join(*paths)
    if not os.path.exists(q_path):
        if create == "folder":
            os.mkdir(q_path)
            custom_print("ok", f"Created the folder - {paths[-1]}")
        elif create in ("config.toml", "mcp_config.json"):
            shutil.copy(q_path + ".sample", q_path)
            custom_print("ok", f'"{create}" created from sample')
            # After first-time creation of config.toml prune the models list to only the required ones
            if create == "config.toml":
                try:
                    _prune_models(q_path)
                except Exception as e:  # pragma: no cover - non critical
                    custom_print("warn", f"Model pruning skipped: {e}")
        elif target and not os.path.exists(os.path.join(paths[0], target)):
            custom_print("error", f'"{target}.sample" is either missing or renamed, please update from source.', 2)
        elif not target:
            custom_print("error", f'No such file or directory: "{q_path}', 2)
    return str(q_path)


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
CONFIG_SAMPLE_PATH = _join_and_check(BASE_PATH, "config.toml.sample", target="config.toml")
CONFIG_PATH = _join_and_check(
    BASE_PATH,
    "config.toml",
    create="config.toml",
)
# Responsible for app-data/version.toml
CONFIG_VERSION_PATH = _join_and_check(BASE_PATH, "app-data", "version.toml")
# Responsible for app-data/local_version.toml
CONFIG_VERSION_PATH_LOCAL = os.path.join(BASE_PATH, "app-data", "local_version.toml")

CHATS_PATH = _join_and_check(BASE_PATH, "chats", create="folder")
ASSISTANTS_PATH = _join_and_check(BASE_PATH, "assistants", create="folder")
IMAGES_PATH = _join_and_check(BASE_PATH, "images", create="folder")


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


def __verify_local_version_config() -> None:
    if not os.path.exists(CONFIG_VERSION_PATH_LOCAL):
        dummy_data = 'version = "0.0.0"'
        with open(CONFIG_VERSION_PATH_LOCAL, "w") as f:
            f.write(dummy_data)


def fetch_version(config_type: str) -> str:
    """
    Fetch version from config file
    :param config_type: Type of config (either local or global)
    :return: config current version as string
    """
    if config_type == "global":
        config = _load_toml(CONFIG_VERSION_PATH)
    else:
        __verify_local_version_config()
        config = _load_toml(CONFIG_VERSION_PATH_LOCAL)
    return config["version"]


def __set_local_version(version: str) -> None:
    config = _load_toml(CONFIG_VERSION_PATH_LOCAL)
    config["version"] = version
    with open(CONFIG_VERSION_PATH_LOCAL, "w") as file:
        toml.dump(config, file)


def check_config_version() -> None:
    """
    Checks if the config file has the current version even if the content seems valid
    :return: Nothing
    """
    global_version = fetch_version("global")
    local_version = fetch_version("local")
    if global_version != local_version:
        # If something is wrong it will exit
        validate_config_files()
        # Otherwise the new version will be applied to the config file.
        __set_local_version(global_version)


def __read_toml_structure(file_path) -> Dict:
    """
    Breaks down the config file structure
    :param file_path: path to config file (and sample)
    """

    def get_structure(value):
        if isinstance(value, dict):
            # Skip models and roles because everyone will have different roles and models
            return {key: get_structure(val) for key, val in value.items() if key not in ["models", "roles"]}
            # return {key: get_structure(val) for key, val in value.items()}
        else:
            return type(value).__name__

    return get_structure(_load_toml(file_path))


def __compare_structures(struct1, struct2) -> List[str]:
    """
    Compares two dictionaries (config structure) and returns the difference.
    :param struct1: config.toml.sample's structure
    :param struct2: config.toml's structure
    :return: The difference between the two dictionaries (structures)
    """

    def compare_helper(dict1, dict2, path=""):
        differences = []
        for key in dict1:
            if key not in dict2:
                differences.append(f"{path}{key} is missing from config.toml!")
            else:
                if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                    differences += compare_helper(dict1[key], dict2[key], path + key + ".")
                elif dict1[key] != dict2[key]:
                    differences.append(
                        f"{path}{key} expects a value of a type `{dict1[key]}`, found `{dict2[key]}` instead!"
                    )

        for key in dict2:
            if key not in dict1:
                differences.append(f"{path}{key} should be removed from config.toml!")

        return differences

    return compare_helper(struct1, struct2)


def validate_config_files() -> None:
    """
    Compare both the config.toml and config.toml.sample (which should always hold the right values)
    And prints and error if something is not right.
    """
    sample = __read_toml_structure(CONFIG_SAMPLE_PATH)
    main = __read_toml_structure(CONFIG_PATH)
    diffs = __compare_structures(sample, main)
    if len(diffs) > 0:
        custom_print("error", "Inconsistency found in configuration file:")
        for diff in diffs:
            print("\t❯", diff)
        # Note that we're exiting here to avoid breaking the chat with the missing entries.
        custom_print("info", "Refer to the config.toml.sample.", 1)
