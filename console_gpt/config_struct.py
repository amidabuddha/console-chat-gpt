"""
The sole purpose of this file is to keep track 
if everything within the config is right during upgrade.
"""

# Define the expected structure
CONFIG_STRUCT = {
    "chat": {
        "structure": {"version": str, "valid": bool, "first_use": bool, "changelog_checksum": str},
        "customizations": {
            "use_emoji": bool,
            "fallback_char": str,
        },
        "defaults": {
            "temperature": int,
            "system_role": str,
            "model": str,
        },
        "features": {
            "model_selector": bool,
            "adjust_temperature": bool,
            "role_selector": bool,
            "save_chat_on_exit": bool,
            "continue_chat": bool,
            "debug": bool,
        },
        "roles": {
            # Ignore the content of 'chat.roles'
        },
        "models": {
            # Ignore the content of 'chat.models'
        },
    }
}
