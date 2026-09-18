"""
ALF Textual user interface.

Provides the interactive terminal front end for ALF's capabilities.
The TUI delegates application logic to the underlying ALF modules and
is responsible for presentation, user interaction, and workspace state.
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Header,
    Label,
    ListItem,
    ListView,
    Static,
)

from alf.command_catalogue import commands
from alf.tui.calc_tui import CalcTUI
from alf.tui.memories_tui import MemoriesTUI
from alf.tui.question_tui import QuestionTUI
from alf.tui.remember_tui import RememberTUI


class ALFTUI(App):
    """Minimal Textual playground."""

    CSS = """
    Screen {
        layout: vertical;
        scrollbar-size: 1 1;
    }

    #main {
        height: 1fr;
    }

    #navigation {
        width: 12%;
        border: solid yellow;
    }

    #navigation ListItem.--highlight {
        text-style: bold;
    }

    #workspace {
        width: 88%;
        height: 1fr;
    }

    .workspace-title {
        height: 3;
        content-align: left middle;
    }

    #memories-list {
        width: 55%;
    }

    #memory-view-actions Button {
        margin-right: 1;
    }

    #memories {
        width: 100%;
        border: solid green;
    }

    #memories Label {
        width: 100%;
        height: auto;
    }

    #memories ListItem {
        border-bottom: solid grey;
        padding-bottom: 1;
    }

    #memory-detail {
        width: 45%;
    }

    #footer {
        height: 3;
        align: right middle;
    }

    #footer-guidance {
        width: 1fr;
        padding: 1 2;
    }

    #quit {
        width: 10;
    }

    Button {
        height: 1;
        border: none;
        padding: 0 1;
    }
    #question-workspace,
    #remember-workspace,
    #memories-workspace
    {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):
            yield ListView(
                *[
                    ListItem(
                        Label(commands[command]["tui"]["title"]),
                        id=f"navigation-{command}",
                    )
                    for command in ("question", "calc", "remember", "memories")
                ],
                id="navigation",
            )

            with Vertical(id="workspace"):
                yield QuestionTUI(id="question-workspace")
                yield CalcTUI(id="calc-workspace")
                yield RememberTUI(id="remember-workspace")
                yield MemoriesTUI(id="memories-workspace")
        with Horizontal(id="footer"):
            yield Static(
                "",
                id="footer-guidance",
            )
            yield Button("Quit", id="quit")


    def on_mount(self) -> None:
        navigation = self.query_one("#navigation", ListView)
        navigation.index = 0
        navigation.focus()

        self.show_question()


    def show_workspace(self, workspace_id: str) -> None:
        question_workspace = self.query_one("#question-workspace")
        calc_workspace = self.query_one("#calc-workspace")
        remember_workspace = self.query_one("#remember-workspace")
        memories_workspace = self.query_one("#memories-workspace")
        footer_guidance = self.query_one("#footer-guidance", Static)

        question_workspace.display = workspace_id == "question"
        calc_workspace.display = workspace_id == "calc"
        remember_workspace.display = workspace_id == "remember"
        memories_workspace.display = workspace_id == "memories"

        footer_guidance.update(commands[workspace_id]["tui"]["guidance"])


    def show_question(self) -> None:
        self.show_workspace("question")


    def show_calc(self) -> None:
        self.show_workspace("calc")


    def show_memories(self) -> None:
        self.show_workspace("memories")


    def show_remember(self) -> None:
        self.show_workspace("remember")


    def calculate_expression(self) -> None:
        self.query_one("#calc-workspace").calculate_expression()


    async def save_remembered_memory(self) -> None:
        await self.query_one("#remember-workspace").save_remembered_memory()


    def ask_question(self) -> None:
        self.query_one("#question-workspace").ask_question()


    async def on_input_submitted(self, event) -> None:
        if event.input.id == "question-input":
            self.query_one("#question-workspace").ask_question()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()

    def show_navigation_command(self, command: str) -> None:
        if command == "question":
            self.show_question()

        elif command == "calc":
            self.show_calc()

        elif command == "remember":
            self.show_remember()

        elif command == "memories":
            self.show_memories()


    def on_list_view_highlighted(
        self,
        event: ListView.Highlighted,
    ) -> None:
        if event.list_view.id != "navigation":
            return

        if event.item is None:
            return

        command = event.item.id.removeprefix("navigation-")
        self.show_navigation_command(command)


    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "navigation":
            command = event.item.id.removeprefix("navigation-")
            self.show_navigation_command(command)
            return

        if event.list_view.id in {
            "calc-examples",
            "calc-symbolic-examples",
        }:
            self.query_one("#calc-workspace").on_list_view_selected(event)


def main() -> None:
    ALFTUI().run()


if __name__ == "__main__":
    main()
