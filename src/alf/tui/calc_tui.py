"""
ALF Calculator TUI workspace.

Provides the Textual interface for ALF's calculator capability.
"""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    Select,
    Static,
)

from alf.calc import CalculationError, calculate
from alf.command_catalogue import commands


class CalcTUI(Horizontal):
    """Textual workspace for performing calculations."""

    DEFAULT_CSS = """
    #calc-workspace {
        height: 1fr;
        layout: horizontal;
    }

    #calc-left {
        width: 55%;
        border: solid green;
        padding: 0 2;
    }

    #calc-right {
        width: 45%;
        border: solid blue;
        padding: 1 2;
    }

    #calc-left .workspace-title {
        height: 1;
    }

    #calc-input {
        height: 3;
    }

    #calc-options {
        height: 1;
        align: left middle;
    }

    #calc-mode {
        width: auto;
        height: auto;
        layout: horizontal;
    }

    #calc-precision {
        width: 1fr;
        height: 3;
        align: right middle;
    }

    #calc-mode RadioButton {
        width: auto;
    }

    #calc-options Label {
        width: auto;
        margin-left: 1;
        margin-right: 1;
    }

    #calc-places {
        width: 10;
        height: 3;
    }

    #calc-controls {
        height: 3;
        border: solid blue;
        align: left middle;
    }

    #calc-controls Button {
        width: 1fr;
    }

    #calc-result {
        height: 1fr;
        border: solid blue;
        padding: 1 2;
    }

    #calc-examples,
    #calc-symbolic-examples {
        height: auto;
        margin: 0 1;
    }

    .calc-example-heading {
        height: 2;
        margin: 1 1 0 1;
        border-bottom: solid $border-blurred;
    }
    """

    def on_mount(self) -> None:
        self.calc_history = []

    def compose(self) -> ComposeResult:
        calc_tui = commands["calc"]["tui"]

        with Vertical(id="calc-left"):
            yield Static(
                calc_tui["title"],
                classes="workspace-title",
            )

            yield Input(
                id="calc-input",
                placeholder=calc_tui["description"],
            )

            with Horizontal(id="calc-options"):
                with RadioSet(
                    id="calc-mode",
                    compact=True,
                ):
                    yield RadioButton(
                        "Numeric",
                        value=True,
                    )
                    yield RadioButton(
                        "Symbolic",
                        id="calc-symbolic",
                    )

                with Horizontal(id="calc-precision"):
                    yield Label("Dec:")
                    yield Select(
                        [
                            ("1", 1),
                            ("2", 2),
                            ("3", 3),
                            ("4", 4),
                            ("5", 5),
                            ("6", 6),
                            ("7", 7),
                            ("8", 8),
                            ("9", 9),
                            ("10", 10),
                        ],
                        value=3,
                        id="calc-places",
                        compact=True,
                    )

            with Horizontal(id="calc-controls"):
                yield Button(
                    "Calculate",
                    id="calc-button",
                )
                yield Button(
                    "Clear",
                    id="calc-clear",
                )

            with VerticalScroll(id="calc-result"):
                yield Static(
                    "The result will appear here.",
                    id="calc-history",
                )

        with Vertical(id="calc-right"):
            yield Static(
                "Try some numerical calculations",
                classes="calc-example-heading",
            )

            example_index = 0
            numerical_items = []

            for group, examples in commands["calc"]["examples"].items():
                if group == "Symbolic mathematics":
                    continue

                numerical_items.append(
                    ListItem(
                        Label(group),
                        classes="calc-example-heading",
                    )
                )

                for example in examples:
                    numerical_items.append(
                        ListItem(
                            Label(
                                example.removeprefix('alf calc "')
                                .removesuffix('"')
                            ),
                            id=f"calc-example-{example_index}",
                        )
                    )
                    example_index += 1

            yield ListView(
                *numerical_items,
                id="calc-examples",
            )

            yield Static(
                "Explore symbolic mathematics",
                classes="calc-example-heading",
            )

            symbolic_items = []

            for index, example in enumerate(
                commands["calc"]["examples"]["Symbolic mathematics"]
            ):
                symbolic_items.append(
                    ListItem(
                        Label(
                            example.removeprefix('alf calc "')
                            .removesuffix('"')
                        ),
                        id=f"calc-example-symbolic-{index}",
                    )
                )

            yield ListView(
                *symbolic_items,
                id="calc-symbolic-examples",
            )

    def calculate_expression(self) -> None:
        expression = self.query_one("#calc-input", Input).value.strip()

        if not expression:
            return

        mode = self.query_one("#calc-mode", RadioSet)
        symbolic = mode.pressed_button.label.plain == "Symbolic"

        places = self.query_one("#calc-places", Select).value

        try:
            calculation = calculate(
                expression,
                symbolic=symbolic,
                places=places,
            )
        except CalculationError as error:
            self.calc_history.append(
                f"{expression}\n{error}"
            )
        else:
            self.calc_history.append(
                f"{expression}\n{calculation}"
            )

        self.query_one("#calc-history", Static).update(
            "\n\n".join(self.calc_history)
        )
        self.query_one("#calc-input", Input).value = ""
        self.query_one("#calc-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "calc-button":
            self.calculate_expression()

        elif event.button.id == "calc-clear":
            self.clear_calculation()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "calc-mode":
            return

        symbolic = event.pressed.label.plain == "Symbolic"

        self.query_one("#calc-places", Select).disabled = symbolic

    def clear_calculation(self) -> None:
        self.calc_history.clear()
        self.query_one("#calc-input", Input).value = ""
        self.query_one("#calc-history", Static).update(
            "The result will appear here."
        )
        self.query_one("#calc-input", Input).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id not in {
            "calc-examples",
            "calc-symbolic-examples",
        }:
            return

        label = event.item.query_one(Label)
        expression = str(label.content)

        symbolic = event.list_view.id == "calc-symbolic-examples"

        mode = self.query_one("#calc-mode", RadioSet)

        if symbolic and mode.pressed_index == 0:
            mode.query_one("#calc-symbolic", RadioButton).value = True
        elif not symbolic and mode.pressed_index == 1:
            mode.query_one(RadioButton).value = True

        input_widget = self.query_one("#calc-input", Input)
        input_widget.value = expression
        input_widget.focus()
