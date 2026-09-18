"""
ALF Question TUI workspace.

Provides the Textual interface for asking questions through ALF's
question capability.
"""

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Static

from alf.command_catalogue import commands
from alf.question import answer_question


class QuestionTUI(Vertical):
    """Textual workspace for asking questions."""

    DEFAULT_CSS = """
    #question-workspace {
        height: 1fr;
    }

    #question-input {
        height: 3;
        border: solid blue;
    }

    #question-controls {
        height: 3;
        margin-top: 0;
        border: solid blue;
        align: left top;
    }

    #detailed-answer-control {
        width: auto;
        height: 1;
    }

    #ask {
        margin-left: 2;
    }

    #question-status {
        width: 1fr;
        height: 3;
        padding: 0 2;
        content-align: left top;
    }

    #answer {
        height: 1fr;
        border: solid blue;
        padding: 1 2;
    }

    #answer-ok {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        question_tui = commands["question"]["tui"]

        yield Static(
            question_tui["title"],
            classes="workspace-title",
        )

        yield Input(
            id="question-input",
            placeholder=question_tui["description"],
        )

        with Horizontal(id="question-controls"):
            with Horizontal(id="detailed-answer-control"):
                yield Checkbox(
                    "Detailed answer",
                    id="detailed-answer",
                    compact=True,
                )

            yield Button("Ask", id="ask")

            yield Static(
                "Ready",
                id="question-status",
            )

        with VerticalScroll(id="answer"):
            yield Static(
                "Your answer will appear here.",
                id="answer-text",
            )

        yield Static(
            "Source: —",
            id="answer-source",
        )

        yield Button("OK", id="answer-ok")

    def ask_question(self) -> None:
        if self.query_one("#ask", Button).disabled:
            return

        question = self.query_one("#question-input", Input).value

        if not question.strip():
            return

        detailed = self.query_one("#detailed-answer", Checkbox).value

        status = self.query_one("#question-status", Static)
        answer = self.query_one("#answer-text", Static)
        source = self.query_one("#answer-source", Static)
        ok_button = self.query_one("#answer-ok", Button)

        status.update("Asking local language model…")
        answer.update("Waiting for answer…")
        source.update("Source: Local language model")
        ok_button.display = False
        self.query_one("#ask", Button).disabled = True

        self.ask_question_worker(
            question,
            detailed,
        )

    @work(thread=True)
    def ask_question_worker(
        self,
        question: str,
        detailed: bool,
    ) -> None:

        def report_progress(message: str) -> None:
            self.app.call_from_thread(
                self.update_question_status,
                message,
            )

        try:
            result = answer_question(
                question,
                verbose=detailed,
                progress=report_progress,
            )
        except Exception as error:
            self.app.call_from_thread(
                self.show_question_error,
                str(error),
            )
            return

        self.app.call_from_thread(
            self.show_question_answer,
            result,
        )

    def update_question_status(self, message: str) -> None:
        self.query_one("#question-status", Static).update(message)

    def show_question_answer(self, result) -> None:
        self.query_one("#question-status", Static).update("Complete")
        self.query_one("#answer-text", Static).update(result.answer)

        source = result.source or "No reliable source"

        self.query_one("#answer-source", Static).update(
            f"Source: {source}"
        )

        self.query_one("#answer-ok", Button).display = True
        self.query_one("#ask", Button).disabled = False

    def show_question_error(self, error: str) -> None:
        self.query_one("#question-status", Static).update("Failed")
        self.query_one("#answer-text", Static).update(
            "I couldn't get an answer to the question."
        )
        self.query_one("#answer-source", Static).update(
            f"Error: {error}"
        )
        self.query_one("#answer-ok", Button).display = True
        self.query_one("#ask", Button).disabled = False

    def clear_question(self) -> None:
        self.query_one("#question-input", Input).value = ""
        self.query_one("#answer-text", Static).update(
            "Your answer will appear here."
        )
        self.query_one("#answer-source", Static).update("Source: —")
        self.query_one("#answer-ok", Button).display = False

    async def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id == "question-input":
            self.ask_question()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ask":
            self.ask_question()

        elif event.button.id == "answer-ok":
            self.clear_question()

        elif event.button.id == "answer-ok":
            self.clear_question()
