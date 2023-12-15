import toml

from console_gpt.config_manager import CONFIG_PATH, write_to_config
from console_gpt.custom_stdout import custom_print

"""
The sole purpose of this file is to keep track 
if everything within the config is right during upgrade.
"""

with open(CONFIG_PATH, 'r') as config_file:
    toml_config = config_file.read()

# Define the expected structure
structure = {
    'chat': {
        'structure': {
            'valid': bool
        },
        'customizations': {
            'use_emoji': bool,
            'fallback_char': str,
        },
        'defaults': {
            'temperature': int,
            'system_role': str,
            'model': str,
        },
        'features': {
            'model_selector': bool,
            'adjust_temperature': bool,
            'role_selector': bool,
            'save_chat_on_exit': bool,
            'continue_chat': bool,
            'debug': bool,
        },
        'roles': {
            # Ignore the content of 'chat.roles'
        },
        'models': {
            # Ignore the content of 'chat.models'
        }
    }
}

# Parse the TOML config
parsed_config = toml.loads(toml_config)


# Validate the structure
def validate_structure(config, expected_structure, parent_key=''):
    warnings = 0
    for key, value in expected_structure.items():
        full_key = f'{parent_key}.{key}' if parent_key else key
        if key not in config:
            custom_print('warn', f'Missing key: {full_key}')
            warnings += 1
        elif isinstance(value, dict):
            warnings += validate_structure(config[key], value, parent_key=full_key)
        elif not isinstance(config[key], value):
            custom_print('error', f'Invalid type for {full_key}')
            warnings += 1
    return warnings


status = validate_structure(parsed_config, structure)
if status == 0:
    custom_print('ok', "Verified and looking fine! You can now proceed with the chat.")
    write_to_config("structure", "valid", new_value=True)
else:
    write_to_config("structure", "valid", new_value=False, group=True)
    # write_to_config("structure", "valid", new_value=False)
    custom_print('info', "Your config file looks wrong, please refer to config.toml.sample", 1)
