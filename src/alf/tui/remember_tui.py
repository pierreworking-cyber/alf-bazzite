"""
ALF Remember TUI workspace.

Provides the Textual interface for saving memories through ALF's
remember capability.
"""

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TextArea,
)

from alf.command_catalogue import commands
from alf.memory import find_related_memory_candidates, remember


class RememberTUI(Vertical):
    """Textual workspace for saving memories."""
    related_search_generation = 0

    DEFAULT_CSS = """
    #remember-workspace {
        height: 1fr;
    }

    #remember-input {
        height: 1fr;
        border: solid blue;
    }

    #remember-controls {
        height: 3;
        margin-top: 0;
        border: solid blue;
        align: left middle;
    }

    #remember-category {
        width: 14;
        height: 3;
    }

    #remember-save {
        width: auto;
        height: 1;
        margin-left: 2;
    }

    #remember-related-title {
        height: 2;
        margin-top: 1;
        border-bottom: solid $border-blurred;
    }

    #remember-related {
        height: 8;
        border: solid blue;
        padding: 1 2;
    }

    #remember-related Horizontal {
        width: 100%;
        height: auto;
    }

    #remember-related Checkbox {
        width: auto;
        height: auto;
    }

    #remember-related Label {
        width: 1fr;
        height: auto;
        text-wrap: nowrap;
    }

    #remember-related ListItem {
        border-bottom: solid grey;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        remember_tui = commands["remember"]["tui"]

        yield Static(
            remember_tui["title"],
            classes="workspace-title",
        )

        yield TextArea(
            id="remember-input",
            placeholder=remember_tui["description"],
        )

        with Horizontal(id="remember-controls"):
            yield Button(
                "Save",
                id="remember-save",
            )
            yield Select(
                [
                    ("Note", "note"),
                    ("Preference", "preference"),
                    ("Decision", "decision"),
                    ("Fact", "fact"),
                ],
                value="note",
                id="remember-category",
                compact=True,
            )

        yield Static(
            "Ready",
            id="remember-status",
        )

        yield Static(
            "Related memories",
            id="remember-related-title",
        )

        yield ListView(
            id="remember-related",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "remember-save":
            await self.save_remembered_memory()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "remember-input":
            return

        content = event.text_area.text.strip()

        self.related_search_generation += 1

        if not content:
            self.clear_related_memories()
            return

        self.update_related_memories(
            content,
            self.related_search_generation,
        )

    def clear_related_memories(self) -> None:
        related = self.query_one("#remember-related", ListView)
        related.clear()

    @work(exclusive="related-memory-search")
    async def update_related_memories(
        self,
        content: str,
        generation: int,
    ) -> None:

        await asyncio.sleep(0.75)

        if generation != self.related_search_generation:
            return

        candidates = find_related_memory_candidates(content)

        if generation != self.related_search_generation:
            return

        related = self.query_one("#remember-related", ListView)
        await related.clear()

        if generation != self.related_search_generation:
            return

        for memory in candidates:
            if generation != self.related_search_generation:
                return

            await related.append(
                ListItem(
                    Horizontal(
                        Checkbox(
                            id=f"related-memory-{memory['id']}",
                            compact=True,
                        ),
                        Label(
                            f"{memory['id']}  "
                            f"{memory['category']:<9} "
                            f"{'* ' if memory['status'] != 'active' else ''}"
                            f"{memory['content']}"
                        ),
                    ),
                    id=f"related-memory-item-{memory['id']}",
                )
            )

    async def save_remembered_memory(self) -> None:
        category = self.query_one("#remember-category", Select).value
        content = self.query_one("#remember-input", TextArea).text.strip()

        status = self.query_one("#remember-status", Static)

        if category is Select.BLANK:
            status.update("Please choose a memory category.")
            return

        if not content:
            status.update("Please enter something to remember.")
            return

        related = self.query_one("#remember-related", ListView)
        related_memory_ids = [
            item.query_one(Checkbox).id.removeprefix("related-memory-")
            for item in related.children
            if item.query_one(Checkbox).value
        ]

        result = remember(
            category,
            content,
            related_memory_ids=",".join(related_memory_ids) or None,
        )

        if result is not True:
            status.update("I couldn't save that memory.")
            return

        self.query_one("#remember-input", TextArea).text = ""
        self.clear_related_memories()
        status.update("Memory saved.")
