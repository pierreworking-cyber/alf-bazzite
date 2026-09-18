import asyncio
import threading

from textual.widgets import Button, Input, ListView

from alf.command_catalogue import commands
from alf.question import QuestionResult
from alf.tui import ALFTUI, DeleteMemoryConfirm
from alf.tui.question_tui import QuestionTUI


def make_sample_memory(memory_id=7, content=None, status="active"):
    return {
        "id": memory_id,
        "created": "2026-01-01 00:00:00",
        "category": "note",
        "status": status,
        "content": content or "A memory that survives the test session.",
        "previous_memory_id": None,
        "related_memory_ids": None,
    }


def make_memory_fakes(
    monkeypatch,
    memories=None,
    remember_result=True,
    related_candidates=(),
):
    """Install fake memory functions so TUI tests avoid the real database.

    Mutation calls are recorded on the returned store so tests can assert
    what the TUI asked ALF to do.
    """

    if memories is None:
        memories = [make_sample_memory()]

    store = {
        "memories": memories,
        "deleted": [],
        "remembered": [],
        "updated": [],
        "archived": [],
        "restored": [],
    }

    async def fake_sleep(_seconds):
        return None

    def fake_find_related_memory_candidates(content, limit=5):
        return list(related_candidates)

    def fake_get_memories(options=None):
        if options is not None and options.get("include_archived"):
            return list(store["memories"])

        return [
            memory
            for memory in store["memories"]
            if memory["status"] != "archived"
        ]

    def fake_get_memory(memory_id):
        return next(
            (memory for memory in store["memories"] if memory["id"] == memory_id),
            None,
        )

    def fake_delete_memory(memory_id):
        store["deleted"].append(memory_id)
        store["memories"] = [
            memory for memory in store["memories"] if memory["id"] != memory_id
        ]
        return True

    def fake_remember(
        category,
        content,
        previous_memory_id=None,
        related_memory_ids=None,
    ):
        store["remembered"].append(
            (category, content, previous_memory_id, related_memory_ids)
        )
        return remember_result

    def fake_update_memory(memory_id, content):
        store["updated"].append((memory_id, content))

        for memory in store["memories"]:
            if memory["id"] == memory_id:
                memory["content"] = content

        return True

    def fake_archive_memory(memory_id):
        store["archived"].append(memory_id)

        for memory in store["memories"]:
            if memory["id"] == memory_id:
                memory["status"] = "archived"

        return True

    def fake_restore_memory(memory_id):
        store["restored"].append(memory_id)

        for memory in store["memories"]:
            if memory["id"] == memory_id:
                memory["status"] = "active"

        return True

    monkeypatch.setattr("alf.tui.memories_tui.get_memories", fake_get_memories)
    monkeypatch.setattr("alf.tui.memories_tui.get_memory", fake_get_memory)
    monkeypatch.setattr("alf.tui.memories_tui.delete_memory", fake_delete_memory)
    monkeypatch.setattr("alf.tui.remember_tui.remember", fake_remember)
    monkeypatch.setattr("alf.tui.memories_tui.update_memory", fake_update_memory)
    monkeypatch.setattr("alf.tui.memories_tui.archive_memory", fake_archive_memory)
    monkeypatch.setattr("alf.tui.memories_tui.restore_memory", fake_restore_memory)
    monkeypatch.setattr(
        "alf.tui.remember_tui.find_related_memory_candidates",
        fake_find_related_memory_candidates,
    )
    monkeypatch.setattr("alf.tui.remember_tui.asyncio.sleep", fake_sleep)

    return store


def test_initial_navigation_shows_question_workspace(monkeypatch):
    make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            await pilot.pause()

            navigation = app.query_one("#navigation", ListView)

            assert navigation.index == 0
            assert app.query_one("#question-workspace").display
            assert not app.query_one("#calc-workspace").display
            assert not app.query_one("#remember-workspace").display
            assert not app.query_one("#memories-workspace").display
            assert (
                app.query_one("#footer-guidance").render().plain
                == commands["question"]["tui"]["guidance"]
            )

    asyncio.run(run_test())


def test_navigation_round_trip_switches_workspaces(monkeypatch):
    make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            navigation = app.query_one("#navigation", ListView)

            await pilot.press("down", "down", "down")
            await pilot.pause()

            assert navigation.index == 3
            assert app.query_one("#memories-workspace").display
            assert not app.query_one("#question-workspace").display
            assert (
                app.query_one("#footer-guidance").render().plain
                == commands["memories"]["tui"]["guidance"]
            )

            await pilot.press("up", "up", "up")
            await pilot.pause()

            assert navigation.index == 0
            assert app.query_one("#question-workspace").display
            assert not app.query_one("#memories-workspace").display
            assert (
                app.query_one("#footer-guidance").render().plain
                == commands["question"]["tui"]["guidance"]
            )

    asyncio.run(run_test())


def test_remember_save_calls_application_and_clears_input(monkeypatch):
    store = make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_remember()
            await pilot.pause()

            app.query_one("#remember-category").value = "preference"
            app.query_one("#remember-input").text = "User prefers terse answers."

            await pilot.click("#remember-save")
            await pilot.pause()

            assert store["remembered"] == [
                (
                    "preference",
                    "User prefers terse answers.",
                    None,
                    None,
                )
            ]
            assert (
                app.query_one("#remember-status").render().plain
                == "Memory saved."
            )
            assert app.query_one("#remember-input").text == ""
            assert len(app.query_one("#remember-related").children) == 0

    asyncio.run(run_test())


def test_remember_empty_content_is_rejected(monkeypatch):
    store = make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_remember()
            await pilot.pause()

            app.query_one("#remember-input").text = "   "

            await pilot.click("#remember-save")
            await pilot.pause()

            assert store["remembered"] == []
            assert (
                app.query_one("#remember-status").render().plain
                == "Please enter something to remember."
            )

            app.query_one("#remember-input").text = "A new memory."
            await app.query_one("#remember-workspace").save_remembered_memory()
            await pilot.pause()

            assert store["remembered"] == [
                ("note", "A new memory.", None, None)
            ]
            assert (
                app.query_one("#remember-status").render().plain
                == "Memory saved."
            )

    asyncio.run(run_test())


def test_memories_select_shows_selected_details(monkeypatch):
    make_memory_fakes(
        monkeypatch,
        memories=[
            make_sample_memory(7, content="First memory."),
            make_sample_memory(12, content="Second memory."),
        ],
    )

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            await pilot.click("#memory-12")
            await pilot.pause()

            details = app.query_one("#details").render().plain

            assert "Memory 12" in details
            assert "Second memory." in details
            assert "First memory." not in details
            assert (
                app.query_one("#memory-archive").label.plain
                == "Archive"
            )

    asyncio.run(run_test())


def test_memories_edit_save_updates_memory(monkeypatch):
    store = make_memory_fakes(
        monkeypatch,
        memories=[make_sample_memory(7, content="Original content.")],
    )

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            await pilot.click("#memory-7")
            await pilot.pause()
            await pilot.click("#memory-edit")
            await pilot.pause()

            editor = app.query_one("#memory-editor")

            assert editor.text == "Original content."
            assert editor.display

            editor.text = "Updated content."

            await pilot.click("#memory-save")
            await pilot.pause()

            assert store["updated"] == [(7, "Updated content.")]
            assert "Updated content." in (
                app.query_one("#details").render().plain
            )
            assert not editor.display
            assert app.query_one("#details").display

    asyncio.run(run_test())


def test_memories_edit_cancel_does_not_update(monkeypatch):
    store = make_memory_fakes(
        monkeypatch,
        memories=[make_sample_memory(7, content="Original content.")],
    )

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            await pilot.click("#memory-7")
            await pilot.pause()
            await pilot.click("#memory-edit")
            await pilot.pause()

            editor = app.query_one("#memory-editor")
            editor.text = "Should not be saved."

            await pilot.click("#memory-cancel")
            await pilot.pause()

            assert store["updated"] == []
            assert "Original content." in (
                app.query_one("#details").render().plain
            )
            assert not editor.display
            assert app.query_one("#details").display

    asyncio.run(run_test())


def test_memories_archive_calls_archive_and_removes_from_active_list(
    monkeypatch,
):
    store = make_memory_fakes(
        monkeypatch,
        memories=[make_sample_memory(7, content="To be archived.")],
    )

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            memories = app.query_one("#memories", ListView)
            memories.index = 0

            app.query_one("#memory-archive", Button).press()
            await pilot.pause()

            assert store["archived"] == [7]
            assert store["memories"][0]["status"] == "archived"
            assert not any(
                child.id == "memory-7"
                for child in app.query_one("#memories").children
            )

    asyncio.run(run_test())


def test_memories_restore_makes_memory_active_again(
    monkeypatch,
):
    store = make_memory_fakes(
        monkeypatch,
        memories=[
            make_sample_memory(
                7,
                content="Archived memory.",
                status="archived",
            )
        ],
    )

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            app.query_one("#memories-all").value = True
            await pilot.pause()

            assert any(
                child.id == "memory-7"
                for child in app.query_one("#memories").children
            )

            memories = app.query_one("#memories", ListView)
            memories.index = 0

            memories.post_message(
            ListView.Selected(
                memories,
                memories.highlighted_child,
                memories.index,
            )
        )
            await pilot.pause()

            assert (
                app.query_one("#memory-archive", Button).label.plain
                == "Restore"
            )

            app.query_one("#memory-archive", Button).press()
            await pilot.pause()

            assert store["restored"] == [7]
            assert store["memories"][0]["status"] == "active"
            assert any(
                child.id == "memory-7"
                for child in app.query_one("#memories").children
            )

    asyncio.run(run_test())


def test_memory_delete_does_not_happen_immediately(monkeypatch):
    store = make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            memories = app.query_one("#memories", ListView)
            memories.index = 0

            app.query_one("#memory-delete", Button).press()
            await pilot.pause()

            assert store["deleted"] == []
            assert isinstance(app.screen, DeleteMemoryConfirm)

    asyncio.run(run_test())


def test_memory_delete_cancel_leaves_memory_intact(monkeypatch):
    store = make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            memories = app.query_one("#memories", ListView)
            memories.index = 0

            app.query_one("#memory-delete", Button).press()
            await pilot.pause()

            app.screen.query_one("#delete-cancel", Button).press()
            await pilot.pause()

            assert store["deleted"] == []
            assert not isinstance(app.screen, DeleteMemoryConfirm)

    asyncio.run(run_test())


def test_memory_delete_confirm_performs_deletion(monkeypatch):
    store = make_memory_fakes(monkeypatch)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.show_memories()
            await pilot.pause()

            memories = app.query_one("#memories", ListView)
            memories.index = 0

            app.query_one("#memory-delete", Button).press()
            await pilot.pause()

            app.screen.query_one("#delete-permanent", Button).press()
            await pilot.pause()

            assert store["deleted"] == [7]
            assert not isinstance(app.screen, DeleteMemoryConfirm)

    asyncio.run(run_test())


def test_question_success_shows_answer_and_re_arms(monkeypatch):
    captured = {}

    def fake_answer_question(question, verbose=False, progress=None):
        captured["arguments"] = (question, verbose)
        return QuestionResult(
            answer="The capital is Paris.",
            source="web",
            research_question="capital of France",
        )

    monkeypatch.setattr("alf.tui.question_tui.answer_question", fake_answer_question)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.query_one("#question-input").value = (
                "What is the capital of France?"
            )

            app.query_one("#question-workspace", QuestionTUI).ask_question()

            worker = next(
                w for w in app.workers if w.name == "ask_question_worker"
            )
            await worker.wait()
            await pilot.pause()

            assert captured["arguments"] == (
                "What is the capital of France?",
                False,
            )
            assert (
                app.query_one("#question-status").render().plain
                == "Complete"
            )
            assert (
                app.query_one("#answer-text").render().plain
                == "The capital is Paris."
            )
            assert (
                app.query_one("#answer-source").render().plain
                == "Source: web"
            )
            assert not app.query_one("#ask", Button).disabled
            assert app.query_one("#answer-ok").display

    asyncio.run(run_test())


def test_question_failure_shows_error_and_re_arms(monkeypatch):
    def fake_answer_question(question, verbose=False, progress=None):
        raise Exception("connection refused")

    monkeypatch.setattr("alf.tui.question_tui.answer_question", fake_answer_question)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            app.query_one("#question-input").value = (
                "What is the capital of France?"
            )

            app.query_one("#question-workspace", QuestionTUI).ask_question()

            worker = next(
                w for w in app.workers if w.name == "ask_question_worker"
            )
            await worker.wait()
            await pilot.pause()

            assert (
                app.query_one("#question-status").render().plain
                == "Failed"
            )
            assert (
                app.query_one("#answer-text").render().plain
                == "I couldn't get an answer to the question."
            )
            assert (
                app.query_one("#answer-source").render().plain
                == "Error: connection refused"
            )
            assert not app.query_one("#ask", Button).disabled
            assert app.query_one("#answer-ok").display
            assert (
                app.query_one("#question-input").value
                == "What is the capital of France?"
            )

    asyncio.run(run_test())


def test_question_second_submission_is_rejected_while_in_flight(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    invocations = []

    def fake_answer_question(question, verbose=False, progress=None):
        invocations.append(question)
        started.set()
        release.wait(timeout=10)
        return QuestionResult(
            answer="The capital is Paris.",
            source="web",
            research_question="capital of France",
        )

    monkeypatch.setattr("alf.tui.question_tui.answer_question", fake_answer_question)

    async def run_test():
        app = ALFTUI()

        async with app.run_test() as pilot:
            input_widget = app.query_one("#question-input", Input)
            input_widget.value = "What is the capital of France?"

            app.query_one("#question-workspace", QuestionTUI).ask_question()

            worker = next(
                w for w in app.workers if w.name == "ask_question_worker"
            )

            for _ in range(5000):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()

            await app.query_one("#question-workspace").on_input_submitted(
                type("Event", (), {"input": input_widget})()
            )

            assert len(invocations) == 1
            assert len(
                [w for w in app.workers if w.name == "ask_question_worker"]
            ) == 1

            release.set()
            await worker.wait()
            await pilot.pause()

            assert len(invocations) == 1
            assert (
                app.query_one("#question-status").render().plain
                == "Complete"
            )
            assert (
                app.query_one("#answer-text").render().plain
                == "The capital is Paris."
            )
            assert not app.query_one("#ask", Button).disabled

    asyncio.run(run_test())
