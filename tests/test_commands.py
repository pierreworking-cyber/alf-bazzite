import pytest

from alf import commands


def test_interpret_memory_selection_accepts_single_id():
    assert commands.interpret_memory_selection("26") == [26]


def test_interpret_memory_selection_expands_range():
    assert commands.interpret_memory_selection("23-26") == [
        23,
        24,
        25,
        26,
    ]


def test_interpret_memory_selection_accepts_reversed_range():
    assert commands.interpret_memory_selection("26-23") == [
        23,
        24,
        25,
        26,
    ]


def test_interpret_memory_selection_accepts_multiple_ranges_and_ids():
    assert commands.interpret_memory_selection("10-12,15,20-21") == [
        10,
        11,
        12,
        15,
        20,
        21,
    ]


def test_interpret_memory_selection_removes_duplicates():
    assert commands.interpret_memory_selection("10-12,11,12-13") == [
        10,
        11,
        12,
        13,
    ]


def test_interpret_memory_selection_rejects_invalid_selection():
    assert commands.interpret_memory_selection("10--12") is None
    assert commands.interpret_memory_selection("10-banana") is None
    assert commands.interpret_memory_selection("0") is None
    assert commands.interpret_memory_selection("10,") is None


def test_interpret_memory_selection_rejects_negative_id():
    assert commands.interpret_memory_selection("-12") is None


def test_delete_command_deletes_single_memory(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "delete_memories",
        lambda memory_ids: {
            "deleted": memory_ids,
            "missing": [],
        },
    )

    monkeypatch.setattr(
        commands,
        "render_memory_deleted",
        lambda memory_id: captured.setdefault(
            "deleted",
            memory_id,
        ),
    )

    commands.delete_command("26")

    assert captured == {
        "deleted": 26,
    }


def test_delete_command_deletes_multiple_memory_ids(monkeypatch):
    captured = {}

    def fake_delete_memories(memory_ids):
        captured["memory_ids"] = memory_ids
        return {
            "deleted": memory_ids,
            "missing": [],
        }

    monkeypatch.setattr(
        commands,
        "delete_memories",
        fake_delete_memories,
    )

    monkeypatch.setattr(
        commands,
        "render_memories_deleted",
        lambda memory_ids: None,
    )

    commands.delete_command("10", "12")

    assert captured["memory_ids"] == [10, 12]


def test_delete_command_deletes_memory_range(monkeypatch):
    captured = {}

    def fake_delete_memories(memory_ids):
        captured["memory_ids"] = memory_ids
        return {
            "deleted": memory_ids,
            "missing": [],
        }

    monkeypatch.setattr(
        commands,
        "delete_memories",
        fake_delete_memories,
    )

    monkeypatch.setattr(
        commands,
        "render_memories_deleted",
        lambda memory_ids: captured.setdefault(
            "deleted",
            memory_ids,
        ),
    )

    commands.delete_command("23-26")

    assert captured["memory_ids"] == [23, 24, 25, 26]
    assert captured["deleted"] == [23, 24, 25, 26]


def test_delete_command_reports_missing_memories(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "delete_memories",
        lambda memory_ids: {
            "deleted": [23, 24],
            "missing": [25],
        },
    )

    monkeypatch.setattr(
        commands,
        "render_memories_deleted",
        lambda memory_ids: output.append(
            ("deleted", memory_ids)
        ),
    )

    monkeypatch.setattr(
        commands,
        "render_memory_missing",
        lambda memory_ids: output.append(
            ("missing", memory_ids)
        ),
    )

    commands.delete_command("23-25")

    assert output == [
        ("deleted", [23, 24]),
        ("missing", [25]),
    ]


def test_delete_command_rejects_invalid_selection(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.delete_command("-12")

    assert output == ["delete"]


def test_relate_command_accepts_multiple_memory_ids(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "relate_memory",
        lambda memory_id, related_memory_ids: (
            captured.append(
                {
                    "memory_id": memory_id,
                    "related_memory_ids": related_memory_ids,
                }
            )
            or related_memory_ids
        ),
    )

    monkeypatch.setattr(
        commands,
        "render_memory_related",
        lambda memory_id, related_memory_ids: None,
    )

    commands.relate_command(
        "47",
        "46,43",
    )

    commands.relate_command(
        "47",
        "46-43,52",
    )

    assert captured == [
        {
            "memory_id": 47,
            "related_memory_ids": "46,43",
        },
        {
            "memory_id": 47,
            "related_memory_ids": "43,44,45,46,52",
        },
    ]


def test_relate_command_rejects_invalid_memory_selection(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_invalid_related_memory",
        lambda related_memory_ids, usage: output.append(
            (related_memory_ids, usage)
        ),
    )

    monkeypatch.setattr(
        commands,
        "relate_memory",
        lambda *arguments: pytest.fail(
            "relate_memory should not be called"
        ),
    )

    commands.relate_command(
        "47",
        "46--43",
    )

    assert output == [
        (
            "46--43",
            "alf relate <id> <ids>",
        )
    ]


def test_archive_command_archives_single_memory(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "archive_memories",
        lambda memory_ids: (
            captured.append(memory_ids)
            or {
                "archived": memory_ids,
                "missing": [],
            }
        ),
    )

    monkeypatch.setattr(
        commands,
        "render_memory_archived",
        lambda memory_id: None,
    )

    commands.archive_command("47")

    assert captured == [[47]]


def test_archive_command_archives_multiple_memory_ids(monkeypatch):
    captured = {}

    def fake_archive_memories(memory_ids):
        captured["memory_ids"] = memory_ids
        return {
            "archived": memory_ids,
            "missing": [],
        }

    monkeypatch.setattr(
        commands,
        "archive_memories",
        fake_archive_memories,
    )

    monkeypatch.setattr(
        commands,
        "render_memories_archived",
        lambda memory_ids: None,
    )

    commands.archive_command("10", "12")

    assert captured["memory_ids"] == [10, 12]


def test_archive_command_archives_memory_selection(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "archive_memories",
        lambda memory_ids: (
            captured.append(memory_ids)
            or {
                "archived": memory_ids,
                "missing": [],
            }
        ),
    )

    monkeypatch.setattr(
        commands,
        "render_memories_archived",
        lambda memory_ids: None,
    )

    commands.archive_command("46-43,52")

    assert captured == [[43, 44, 45, 46, 52]]


def test_archive_command_rejects_invalid_memory_selection(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    monkeypatch.setattr(
        commands,
        "archive_memories",
        lambda *arguments: pytest.fail(
            "archive_memories should not be called"
        ),
    )

    commands.archive_command("46--43")

    assert output == ["archive"]
