
from alf import memory


def test_database_migrates_schema_from_version_one(database):
    connection = memory.sqlite3.connect(database)

    connection.execute(
        """
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            previous_memory_id INTEGER,
            related_memory_ids TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO memories (created, category, content)
        VALUES (?, ?, ?)
        """,
        ("2026-01-01 12:00:00", "note", "Existing Austerlitz memory."),
    )

    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    with memory.get_connection() as connection:
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        results = connection.execute(
            """
            SELECT rowid
            FROM memory_fts
            WHERE memory_fts MATCH ?
            """,
            ("Austerlitz",),
        ).fetchall()

        mindmap_tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name IN ('mindmaps', 'mindmap_documents')
            ORDER BY name
            """
        ).fetchall()

    assert version == 8
    assert results == [(1,)]
    assert mindmap_tables == [
        ("mindmap_documents",),
        ("mindmaps",),
    ]


def test_database_migrates_mindmaps_from_version_four(database):
    connection = memory.sqlite3.connect(database)

    connection.execute(
        """
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            previous_memory_id INTEGER,
            related_memory_ids TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE mindmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            project TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE mindmap_documents (
            mindmap_id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            FOREIGN KEY (mindmap_id)
                REFERENCES mindmaps(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE mindmap_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE mindmap_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            FOREIGN KEY (category_id)
                REFERENCES mindmap_categories(id)
        )
        """
    )

    connection.execute(
        """
        INSERT INTO mindmaps (
            category,
            project,
            status,
            created,
            modified
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Uncategorised",
            "Garden",
            "active",
            "2026-08-25 10:00:00",
            "2026-08-25 11:00:00",
        ),
    )

    mindmap_id = connection.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO mindmap_documents (
            mindmap_id,
            content
        )
        VALUES (?, ?)
        """,
        (
            mindmap_id,
            '{"meta":{"name":"Garden"},"format":"node_array","data":[]}',
        ),
    )

    connection.execute(
        """
        INSERT INTO mindmaps (
            category,
            project,
            status,
            created,
            modified
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "House",
            "Home",
            "active",
            "2026-08-25 12:00:00",
            "2026-08-25 13:00:00",
        ),
    )

    second_mindmap_id = connection.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO mindmap_documents (
            mindmap_id,
            content
        )
        VALUES (?, ?)
        """,
        (
            second_mindmap_id,
            '{"meta":{"name":"Home"},"format":"node_array","data":[]}',
        ),
    )

    connection.execute("PRAGMA user_version = 4")
    connection.commit()
    connection.close()

    with memory.get_connection() as connection:
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        category = connection.execute(
            """
            SELECT id, name
            FROM mindmap_categories
            WHERE name = ?
            """,
            ("Uncategorised",),
        ).fetchone()

        mindmap = connection.execute(
            """
            SELECT category_id, name
            FROM mindmaps
            WHERE id = ?
            """,
            (mindmap_id,),
        ).fetchone()

        document = connection.execute(
            """
            SELECT content
            FROM mindmap_documents
            WHERE mindmap_id = ?
            """,
            (mindmap_id,),
        ).fetchone()

        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(mindmap_categories)"
            ).fetchall()
        ]

        positions = connection.execute(
            """
            SELECT name, position
            FROM mindmap_categories
            ORDER BY position
            """
        ).fetchall()

    assert version == 8
    assert category is not None
    assert mindmap[0] == category[0]
    assert mindmap[1] == "Garden"
    assert document[0] == (
        '{"meta":{"name":"Garden"},"format":"node_array","data":[]}'
    )
    assert "position" in columns
    assert positions == [("Uncategorised", 0), ("House", 1)]

    categories = memory.get_mindmap_categories()
    assert [category["name"] for category in categories] == [
        "Uncategorised",
        "House",
    ]
    assert categories[0]["position"] == 0
    assert categories[1]["position"] == 1


def test_database_schema_version(database):
    with memory.get_connection() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == memory.SCHEMA_VERSION


def test_database_migrates_memory_categories_from_version_seven(database):
    connection = memory.sqlite3.connect(database)

    connection.execute(
        """
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            previous_memory_id INTEGER,
            related_memory_ids TEXT
        )
        """
    )

    connection.execute(
        """
        INSERT INTO memories (created, category, content)
        VALUES (?, ?, ?)
        """,
        (
            "2026-09-01 12:00:00",
            "note",
            "Existing Linux memory.",
        ),
    )

    connection.execute("PRAGMA user_version = 7")
    connection.commit()
    connection.close()

    with memory.get_connection() as connection:
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(memories)"
            ).fetchall()
        ]

        memory_row = connection.execute(
            """
            SELECT content, memory_category_id
            FROM memories
            WHERE id = 1
            """
        ).fetchone()

    assert version == 8
    assert "memory_categories" in tables
    assert "memory_category_id" in columns
    assert memory_row == (
        "Existing Linux memory.",
        None,
    )
