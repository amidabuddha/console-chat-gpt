from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, TextArea

from console_gpt.catch_errors import eof_wrapper


class MultilinePromptApp(App):
    """Textual app for handling multiline prompts."""

    CSS = """
    Screen {
        align: center middle;
    }

    #dialog {
        padding: 1 2;
        border: heavy $background 80%;
        height: auto;
        width: 90%;
        max-width: 120;
        min-width: 40;
        layout: vertical;
    }

    #additional_input_area {
        width: 100%;
    }

    #multiline_input {
        width: 100%;
        height: 15;
        min-height: 5;
        max-height: 30;
    }

    #output_label {
        background: $error 20%;
        color: $error;
        margin: 1;
        padding: 1;
        border: round $error;
        text-align: center;
        text-style: bold;
        height: auto;
        display: none;
    }

    #output_label.show {
        display: block;
    }

    #info_label {
        background: $success 20%;
        color: $success;
        margin: 1;
        border: none;
        text-align: center;
        text-style: bold;
        height: 1;
        display: none;
        width: 100%;
    }

    #info_label.show {
        display: block;
    }

    TextArea {
        width: 100%;
    }

    TextArea:focus {
        border: tall $accent !important;
    }

    #additional_placeholder, #multiline_placeholder {
        color: $text;
        padding-left: 1;
        text-style: bold;
    }

    .buttons {
        width: 100%;
        height: auto;
        align: center bottom;
        padding: 1;
    }

    Button {
        height: 1;
        border: none;
    }
    """

    multiline_data: str = reactive("")
    additional_data: Optional[str] = reactive(None)

    def show_error(self, message: str) -> None:
        """Display an error message."""
        output_label = self.query_one("#output_label")
        output_label.update(f"{message}")
        output_label.add_class("show")

    def clear_error(self) -> None:
        """Clear the error message."""
        output_label = self.query_one("#output_label")
        output_label.update("")
        output_label.remove_class("show")

    def clear_info(self) -> None:
        """Clear the info message."""
        info_label = self.query_one("#info_label")
        info_label.remove_class("show")

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Vertical(
            Label("💡 Use <TAB> to navigate and CTRL+Q or 'Exit' to quit.", id="info_label"),
            Static("", id="output_label"),
            Input(placeholder="Instructions or actions to perform", id="additional_input_area"),
            Label("Enter multiline text here:", id="multiline_placeholder"),
            TextArea(id="multiline_input", show_line_numbers=True),
            Horizontal(
                Button("Submit", id="submit_button", variant="primary", disabled=True),
                Button("Exit", id="exit_button", variant="default"),
                classes="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Enable both text areas on mount and show info label."""
        self.query_one("#additional_input_area").disabled = False
        self.query_one("#multiline_input").disabled = False
        self.query_one("#additional_input_area").focus()
        self.query_one("#info_label").add_class("show")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle text changes in TextArea widgets."""
        self.clear_error()
        self.clear_info()

        self.query_one("#submit_button").disabled = not event.text_area.text
        self.multiline_data = event.text_area.text

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle text changes in TextArea widgets."""
        self.clear_error()
        self.clear_info()

        self.additional_data = event.input.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit_button":
            self.submit_data()
        elif event.button.id == "exit_button":
            self.multiline_data = ""
            self.additional_data = None
            self.exit((self.additional_data, self.multiline_data))

    def clean_up_input(self, input_text: str) -> str:
        """Clean up the input text by removing leading and trailing whitespaces."""
        return input_text.strip()

    def submit_data(self):
        """Submit the data after validation."""
        multiline_input = self.query_one("#multiline_input")
        additional_input = self.query_one("#additional_input_area")

        cleaned_multiline_data = self.clean_up_input(multiline_input.text)
        cleaned_additional_data = self.clean_up_input(additional_input.value) if additional_input.value else None

        if not cleaned_multiline_data:
            self.show_error("Main text field cannot be empty!")
            multiline_input.focus()
            return

        if cleaned_additional_data == "":
            self.show_error("Additional info cannot be just spaces or new lines!")
            additional_input.focus()
            return

        self.exit((cleaned_additional_data, cleaned_multiline_data))


@eof_wrapper
def multiline_prompt() -> tuple[Optional[str], str]:
    """Multiline prompt which allows writing on multiple lines without
    "Enter" (Return) interrupting your input.

    :return: Tuple containing additional data (Optional[str]) and multiline data (str)
    """
    app = MultilinePromptApp()
    try:
        additional_data, multiline_data = app.run()
    except TypeError:
        return None, ""

    return additional_data, multiline_data
