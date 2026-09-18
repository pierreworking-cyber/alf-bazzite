"""Tests for mind map persistence and category management."""

from alf import memory


def test_create_mindmap_category(database):
    category_id = memory.create_mindmap_category("House")

    assert category_id == 1

    with memory.get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, status
            FROM mindmap_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

    assert row[0] == 1
    assert row[1] == "House"
    assert row[2] == "active"


def test_create_duplicate_mindmap_category_returns_duplicate(database):
    memory.create_mindmap_category("House")

    result = memory.create_mindmap_category("House")

    assert result == "duplicate"

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == ["House"]
    assert [category["position"] for category in categories] == [0]


def test_create_uncategorised_mindmap_category_succeeds(database):
    category_id = memory.create_mindmap_category("Uncategorised")

    assert isinstance(category_id, int)

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == ["Uncategorised"]
    assert [category["position"] for category in categories] == [0]


def test_create_duplicate_uncategorised_is_rejected(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")

    result = memory.create_mindmap_category("Uncategorised")

    assert result == "duplicate"

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_get_mindmap_categories(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "House",
        "Events",
    ]


def test_get_mindmap_categories_preserves_creation_order(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")
    memory.create_mindmap_category("Garden")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "House",
        "Events",
        "Garden",
    ]


def test_move_mindmap_category(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")
    memory.create_mindmap_category("Garden")

    garden = next(
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "Garden"
    )

    result = memory.move_mindmap_category(garden["id"], 1)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "House",
        "Garden",
        "Events",
    ]


def test_move_mindmap_category_to_same_position(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")
    memory.create_mindmap_category("Garden")

    result = memory.move_mindmap_category(2, 1)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "House",
        "Events",
        "Garden",
    ]


def test_move_mindmap_category_down(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")
    memory.create_mindmap_category("Garden")

    result = memory.move_mindmap_category(1, 2)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Events",
        "Garden",
        "House",
    ]


def test_move_mindmap_category_cannot_move_to_position_zero(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    result = memory.move_mindmap_category(2, 0)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
        "Events",
    ]


def test_uncategorised_cannot_be_moved(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    result = memory.move_mindmap_category(1, 2)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
        "Events",
    ]


def test_uncategorised_stays_at_top_when_other_category_moves(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    house = next(
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "House"
    )

    result = memory.move_mindmap_category(house["id"], 2)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Events",
        "House",
    ]


def test_move_missing_mindmap_category(database):
    result = memory.move_mindmap_category(999, 0)

    assert result is False


def test_lazy_uncategorised_from_create_mindmap_gets_position_zero(
    database,
):
    memory.create_mindmap(
        "Uncategorised",
        "New Mindmap",
        '{"meta":{"name":"New Mindmap"},"format":"node_array","data":[]}',
    )

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == ["Uncategorised"]
    assert [category["position"] for category in categories] == [0]

    memory.create_mindmap_category("Work")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Work",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_lazy_category_not_uncategorised_gets_integer_position(database):
    memory.create_mindmap(
        "Vacation",
        "Beach",
        '{"meta":{"name":"Beach"},"format":"node_array","data":[]}',
    )

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == ["Vacation"]
    assert [category["position"] for category in categories] == [0]


def test_multiple_lazy_categories_get_sequential_positions(database):
    memory.create_mindmap("Vacation", "Beach", "{}")
    memory.create_mindmap("Notes", "Things", "{}")
    memory.create_mindmap("House", "Plans", "{}")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Vacation",
        "Notes",
        "House",
    ]
    assert [category["position"] for category in categories] == [0, 1, 2]


def test_uncategorised_stays_position_zero_when_created_first(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
        "Events",
    ]
    assert [category["position"] for category in categories] == [0, 1, 2]


def test_uncategorised_takes_position_zero_when_created_after_lazy_categories(
    database,
):
    memory.create_mindmap("Vacation", "Beach", "{}")
    memory.create_mindmap("Notes", "Things", "{}")

    memory.create_mindmap_category("Uncategorised")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Vacation",
        "Notes",
    ]
    assert [category["position"] for category in categories] == [0, 1, 2]


def test_uncategorised_takes_position_zero_when_lazily_created(database):
    memory.create_mindmap("Vacation", "Beach", "{}")
    memory.create_mindmap_category("House")

    memory.create_mindmap("Uncategorised", "Junk", "{}")

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Vacation",
        "House",
    ]
    assert [category["position"] for category in categories] == [0, 1, 2]


def test_reorder_lazily_created_category(database):
    memory.create_mindmap("Notes", "Things", "{}")
    memory.create_mindmap("Vacation", "Beach", "{}")
    memory.create_mindmap("House", "Plans", "{}")

    house = next(
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "House"
    )

    result = memory.move_mindmap_category(house["id"], 1)

    assert result is True

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Notes",
        "House",
        "Vacation",
    ]
    assert [category["position"] for category in categories] == [0, 1, 2]


def test_delete_introduces_uncategorised_at_position_zero(database):
    memory.create_mindmap_category("Work")
    events_id = memory.create_mindmap_category("Events")

    memory.delete_mindmap_category(events_id)

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Work",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_deleting_middle_category_compacts_positions(database):
    memory.create_mindmap_category("Uncategorised")
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    house = [
        category
        for category in memory.get_mindmap_categories()
        if category["name"] == "House"
    ][0]

    memory.delete_mindmap_category(house["id"])

    categories = memory.get_mindmap_categories()

    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "Events",
    ]
    assert [category["position"] for category in categories] == [0, 1]


def test_get_mindmaps_excludes_archived(database):
    mindmap_id = memory.create_mindmap(
        "House",
        "Plans",
        '{"meta":{"name":"Plans"},"format":"node_array","data":[]}',
    )

    assert len(memory.get_mindmaps()) == 1

    with memory.get_connection() as connection:
        connection.execute(
            """
            UPDATE mindmaps
            SET status = 'archived'
            WHERE id = ?
            """,
            (mindmap_id,),
        )

    assert memory.get_mindmaps() == []


def test_get_mindmap_categories_returns_empty_list(database):
    assert memory.get_mindmap_categories() == []


def test_update_mindmap_category(database):
    memory.create_mindmap_category("House")

    result = memory.update_mindmap_category(
        1,
        name="Home",
    )

    assert result is True

    category = memory.get_mindmap_categories()[0]

    assert category["name"] == "Home"
    assert category["status"] == "active"


def test_update_missing_mindmap_category(database):
    result = memory.update_mindmap_category(
        999,
        name="Missing category",
    )

    assert result is False


def test_update_mindmap_category_duplicate_name_is_rejected(database):
    memory.create_mindmap_category("House")
    memory.create_mindmap_category("Events")

    result = memory.update_mindmap_category(
        2,
        name="House",
    )

    assert result == "duplicate"


def test_update_mindmap_category_to_reserved_name_is_rejected(database):
    memory.create_mindmap_category("House")

    result = memory.update_mindmap_category(
        1,
        name="Uncategorised",
    )

    assert result == "duplicate"


def test_uncategorised_category_cannot_be_renamed(database):
    uncat_id = memory.create_mindmap_category("Uncategorised")

    result = memory.update_mindmap_category(
        uncat_id,
        name="Renamed",
    )

    assert result is False

    category = memory.get_mindmap_categories()[0]
    assert category["name"] == "Uncategorised"
    assert category["position"] == 0


def test_delete_mindmap_category(database):
    category_id = memory.create_mindmap_category("House")

    result = memory.delete_mindmap_category(category_id)

    assert result is True
    assert [category["name"] for category in memory.get_mindmap_categories()] == [
        "Uncategorised"
    ]


def test_delete_missing_mindmap_category(database):
    assert memory.delete_mindmap_category(999) is False


def test_delete_mindmap_category_moves_maps_to_uncategorised(database):
    category_id = memory.create_mindmap_category("Birthday")
    mindmap_id = memory.create_mindmap(
        "Birthday",
        "Party plan",
        '{"meta":{"name":"Party plan"},"format":"node_array","data":[]}',
    )

    result = memory.delete_mindmap_category(category_id)

    assert result is True
    assert "Birthday" not in [
        category["name"]
        for category in memory.get_mindmap_categories()
    ]

    moved = memory.get_mindmap(mindmap_id)

    assert moved is not None
    assert moved["category"] == "Uncategorised"


def test_create_mindmap(database):
    mindmap_id = memory.create_mindmap(
        "House",
        "Living room redecorate",
        "<map><node>Living room</node></map>",
    )

    assert mindmap_id == 1


def test_get_mindmaps(database):
    memory.create_mindmap(
        "House",
        "Living room redecorate",
        "<map><node>Living room</node></map>",
    )
    memory.create_mindmap(
        "Events",
        "Sue birthday",
        "<map><node>Sue birthday</node></map>",
    )

    mindmaps = memory.get_mindmaps()

    assert [item["id"] for item in mindmaps] == [1, 2]
    assert [item["category"] for item in mindmaps] == ["House", "Events"]
    assert [item["name"] for item in mindmaps] == [
        "Living room redecorate",
        "Sue birthday",
    ]


def test_get_mindmaps_returns_empty_list(database):
    assert memory.get_mindmaps() == []


def test_update_mindmap(database):
    memory.create_mindmap(
        "House",
        "Living room redecorate",
        "<map><node>Living room</node></map>",
    )

    result = memory.update_mindmap(
        1,
        category="House",
        name="Living room finished",
        status="active",
        content="<map><node>Finished living room</node></map>",
    )

    assert result is True

    mindmap = memory.get_mindmap(1)

    assert mindmap["category"] == "House"
    assert mindmap["name"] == "Living room finished"
    assert mindmap["status"] == "active"
    assert mindmap["content"] == "<map><node>Finished living room</node></map>"


def test_update_missing_mindmap(database):
    result = memory.update_mindmap(
        999,
        category="House",
        name="Missing map",
        status="active",
        content="<map><node>Missing</node></map>",
    )

    assert result is False


def test_delete_mindmap(database):
    memory.create_mindmap(
        "House",
        "Living room redecorate",
        "<map><node>Living room</node></map>",
    )

    result = memory.delete_mindmap(1)

    assert result is True
    assert memory.get_mindmap(1) is None

    with memory.get_connection() as connection:
        document = connection.execute(
            """
            SELECT mindmap_id
            FROM mindmap_documents
            WHERE mindmap_id = 1
            """
        ).fetchone()

    assert document is None


def test_delete_missing_mindmap(database):
    assert memory.delete_mindmap(999) is False

