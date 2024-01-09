from hashlib import sha256
from os.path import join

from console_gpt.config_manager import (BASE_PATH, fetch_variable,
                                        write_to_config)
from console_gpt.custom_stdout import markdown_print

CHANGELOG_PATH = join(BASE_PATH, "CHANGELOG.md")


def get_changelog() -> None:
    """
    Get the data of the CHANGELOG.md
    :return: config current version as string
    """
    if not _compare_checksums():
        with open(CHANGELOG_PATH, "r") as f:
            data = f.readlines()
        if data not in [None, [], ""]:
            markdown_print("\n".join(data), "Changelog")


def _generate_checksum() -> str:
    checksum = sha256()

    with open(CHANGELOG_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            checksum.update(chunk)

    return checksum.hexdigest()


def _compare_checksums() -> bool:
    new_checksum = _generate_checksum()
    current_checksum = fetch_variable("structure", "changelog_checksum", auto_exit=False)
    if not current_checksum or (new_checksum != current_checksum):
        write_to_config("structure", "changelog_checksum", new_value=new_checksum)
        return False
    return True
