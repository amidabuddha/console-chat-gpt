from questionary import Style

help_options = {
    "help": "Prints all available commands.",
    # "cost": "Prints the costs of the current chat.",
    # "edit": "Prints the last prompt so you can edit it.",
    "exit": "Exits the chat.",
    "file": "Allows you to upload a file content to the chat.",
    "image": "Allows you to upload an image [Supported by gpt-4-turbo and anthropic models].",
    "flush": "Start the chat all over again.",
    "format": "Allows you to write multiline messages.",
    "save": "Saves the chat to a given file.",
    "settings": "Manage available features.",
}

style = Style(
    [
        ("qmark", "fg:#86cdfc bold"),
        ("question", "fg:#ffdb38 bold"),
        ("answer", "fg:#69faff bold"),
    ]
)

custom_style = Style(
    [
        ("question", "fg:#ffdb38 bold"),
        ("answer", "fg:#69faff"),  # answer color
        ("selected", "fg:#ffffff bg:#000000 bold"),  # selected text color
    ]
)
