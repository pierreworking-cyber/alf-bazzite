"""Web tests for the mind map web API."""

import pytest

from alf import memory
from alf.web import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DATABASE", tmp_path / "web.db")
    return app.test_client()


def _create_category(client, name):
    response = client.post(
        "/mindmap-categories",
        json={"name": name},
    )
    assert response.status_code == 200
    return response.get_json()["id"]


def _category_names():
    return [category["name"] for category in memory.get_mindmap_categories()]


def test_creating_category_succeeds(client):
    response = client.post(
        "/mindmap-categories",
        json={"name": "House"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"id": 1, "name": "House"}


def test_creating_duplicate_category_returns_conflict(client):
    _create_category(client, "House")

    response = client.post(
        "/mindmap-categories",
        json={"name": "House"},
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "Mind map category name is already in use"
    }

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == ["House"]
    assert [category["position"] for category in categories] == [0]


def test_creating_existing_uncategorised_returns_conflict(client):
    _create_category(client, "Uncategorised")
    _create_category(client, "House")

    response = client.post(
        "/mindmap-categories",
        json={"name": "Uncategorised"},
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "Mind map category name is already in use"
    }

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_renaming_category_to_existing_name_returns_conflict(client):
    _create_category(client, "House")
    _create_category(client, "Events")

    response = client.patch(
        "/mindmap-categories/2",
        json={"name": "House"},
    )

    assert response.status_code == 409
    assert _category_names() == ["House", "Events"]


def test_renaming_category_to_uncategorised_returns_conflict_when_row_exists(
    client,
):
    memory.create_mindmap_category("Uncategorised")
    _create_category(client, "House")

    response = client.patch(
        "/mindmap-categories/2",
        json={"name": "Uncategorised"},
    )

    assert response.status_code == 409


def test_renaming_category_to_uncategorised_returns_conflict_without_row(
    client,
):
    _create_category(client, "House")

    response = client.patch(
        "/mindmap-categories/1",
        json={"name": "Uncategorised"},
    )

    assert response.status_code == 409


def test_renaming_category_succeeds(client):
    _create_category(client, "House")

    response = client.patch(
        "/mindmap-categories/1",
        json={"name": "Work"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"updated": True}
    assert _category_names() == ["Work"]


def test_renaming_missing_category_returns_not_found(client):
    response = client.patch(
        "/mindmap-categories/9999",
        json={"name": "Work"},
    )

    assert response.status_code == 404


def _create_memory():
    memory.remember(
        "note",
        "Test memory.",
    )

    with memory.get_connection() as connection:
        return connection.execute(
            "SELECT id FROM memories ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]

def _create_mindmap(client):
    _create_category(client, "House")

    response = client.post(
        "/mindmaps/save",
        json={
            "category": "House",
            "name": "Plans",
            "content": '{"meta":{"name":"Plans"},"format":"node_array","data":[]}',
        },
    )
    assert response.status_code == 200
    return response.get_json()["id"]


def test_memories_preserves_preview_lines_on_save(client):
    memory_id = _create_memory()

    response = client.post(
        "/memories",
        data={
            "memory_id": str(memory_id),
            "content": "Updated memory.",
            "preview_lines": "5",
        },
    )

    assert response.status_code == 302
    assert "preview_lines=5" in response.location


def test_memories_preserves_preview_lines_on_archive(client):
    memory_id = _create_memory()

    response = client.post(
        "/memories/archive",
        data={
            "memory_id": str(memory_id),
            "preview_lines": "5",
        },
    )

    assert response.status_code == 302
    assert "preview_lines=5" in response.location


def test_memories_preserves_preview_lines_on_restore(client):
    memory_id = _create_memory()

    client.post(
        "/memories/archive",
        data={"memory_id": str(memory_id)},
    )

    response = client.post(
        "/memories/restore",
        data={
            "memory_id": str(memory_id),
            "preview_lines": "5",
        },
    )

    assert response.status_code == 302
    assert "preview_lines=5" in response.location


def test_memories_preserves_preview_lines_on_delete(client):
    memory_id = _create_memory()

    response = client.post(
        "/memories/delete",
        data={
            "memory_id": str(memory_id),
            "preview_lines": "5",
        },
    )

    assert response.status_code == 302
    assert "preview_lines=5" in response.location


def test_deleting_mindmap_via_delete_endpoint(client):
    mindmap_id = _create_mindmap(client)

    response = client.post(f"/mindmaps/{mindmap_id}/delete")

    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}
    assert memory.get_mindmap(mindmap_id) is None


def test_deleting_missing_mindmap_via_delete_endpoint(client):
    response = client.post("/mindmaps/9999/delete")

    assert response.status_code == 404


def test_old_mindmap_archive_endpoint_is_removed(client):
    created = _create_mindmap(client)

    response = client.post(f"/mindmaps/{created}/archive")

    assert response.status_code == 404


def test_saving_mindmap_succeeds(client):
    response = client.post(
        "/mindmaps/save",
        json={
            "category": "House",
            "name": "Plans",
            "content": '{"meta":{"name":"Plans"},"format":"node_array","data":[]}',
        },
    )

    assert response.status_code == 200
    mindmap_id = response.get_json()["id"]
    assert memory.get_mindmap(mindmap_id)["name"] == "Plans"


def test_saving_mindmap_without_data_returns_bad_request(client):
    response = client.post("/mindmaps/save", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "No mind map data supplied"}


def test_saving_missing_mindmap_returns_not_found(client):
    _create_mindmap(client)

    response = client.post(
        "/mindmaps/save",
        json={
            "id": 9999,
            "category": "House",
            "name": "Plans",
            "content": "{}",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Mind map not found"}


def test_saving_mindmap_with_missing_category_returns_not_found(client):
    mindmap_id = _create_mindmap(client)

    response = client.post(
        "/mindmaps/save",
        json={
            "id": mindmap_id,
            "category": "Events",
            "name": "Plans",
            "content": "{}",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Mind map category not found"
    }

    saved = memory.get_mindmap(mindmap_id)
    assert saved["category"] == "House"
    assert saved["name"] == "Plans"


def test_updating_existing_mindmap_succeeds(client):
    mindmap_id = _create_mindmap(client)

    response = client.post(
        "/mindmaps/save",
        json={
            "id": mindmap_id,
            "category": "House",
            "name": "Renamed Plans",
            "content": (
                '{"meta":{"name":"Renamed Plans"},'
                '"format":"node_array","data":[]}'
            ),
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"id": mindmap_id}

    saved = memory.get_mindmap(mindmap_id)
    assert saved["name"] == "Renamed Plans"
    assert saved["category"] == "House"


def test_moving_mindmap_succeeds(client):
    created = _create_mindmap(client)
    _create_category(client, "Events")

    response = client.post(
        f"/mindmaps/{created}/move",
        json={"category": "Events"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"moved": True}
    assert memory.get_mindmap(created)["category"] == "Events"


def test_moving_mindmap_without_category_returns_bad_request(client):
    response = client.post("/mindmaps/1/move", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "No category supplied"}

    response = client.post(
        "/mindmaps/1/move",
        json={"category": "   "},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "No category supplied"}


def test_moving_missing_mindmap_returns_not_found(client):
    _create_category(client, "House")

    response = client.post(
        "/mindmaps/9999/move",
        json={"category": "House"},
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Mind map or category not found"
    }


def test_moving_category_succeeds(client):
    _create_category(client, "House")
    _create_category(client, "Events")
    _create_category(client, "Work")

    response = client.post(
        "/mindmap-categories/1/move",
        json={"position": 2},
    )

    assert response.status_code == 200
    assert response.get_json() == {"moved": True}
    assert _category_names() == ["Events", "Work", "House"]


def test_moving_category_without_position_returns_bad_request(client):
    _create_category(client, "House")

    response = client.post("/mindmap-categories/1/move", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "No position supplied"}

    response = client.post(
        "/mindmap-categories/1/move",
        json={"position": -1},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid position"}

    response = client.post(
        "/mindmap-categories/1/move",
        json={"position": "early"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid position"}


def test_moving_missing_category_returns_not_found(client):
    response = client.post(
        "/mindmap-categories/9999/move",
        json={"position": 0},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Mind map category not found"}


def test_deleting_category_succeeds(client):
    category_id = _create_category(client, "House")

    response = client.delete(f"/mindmap-categories/{category_id}")

    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}

    names = _category_names()

    assert "House" not in names
    assert names == ["Uncategorised"]


def test_deleting_category_with_mindmap_moves_map_to_uncategorised(client):
    mindmap_id = _create_mindmap(client)
    house = next(
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "House"
    )

    response = client.delete(f"/mindmap-categories/{house['id']}")

    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}

    moved = memory.get_mindmap(mindmap_id)

    assert moved["category"] == "Uncategorised"


def test_deleting_last_ordinary_category_creates_uncategorised(client):
    category_id = _create_category(client, "House")

    response = client.delete(f"/mindmap-categories/{category_id}")

    assert response.status_code == 200

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised"
    ]
    assert [category["position"] for category in categories] == [0]


def test_deleting_uncategorised_returns_bad_request(client):
    uncat_id = _create_category(client, "Uncategorised")

    response = client.delete(f"/mindmap-categories/{uncat_id}")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Uncategorised cannot be modified"
    }

    assert _category_names() == ["Uncategorised"]


def test_deleting_missing_category_returns_not_found(client):
    response = client.delete("/mindmap-categories/9999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Mind map category not found"}


def test_deleting_middle_category_compacts_positions_via_api(client):
    _create_category(client, "Uncategorised")
    _create_category(client, "House")
    _create_category(client, "Events")

    house = next(
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "House"
    )

    response = client.delete(f"/mindmap-categories/{house['id']}")

    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Events",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_renaming_uncategorised_returns_bad_request(client):
    uncat_id = _create_category(client, "Uncategorised")

    response = client.patch(
        f"/mindmap-categories/{uncat_id}",
        json={"name": "House"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Uncategorised cannot be modified"
    }

    category = memory.get_mindmap_categories()[0]

    assert category["name"] == "Uncategorised"
    assert category["position"] == 0
