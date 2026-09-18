"""
Memory taxonomy storage and category management.

Memory categories are user-defined organisational categories used to
group and organise persistent memories. They form a separate
hierarchical taxonomy from ALF's fixed memory types, such as `note`,
`fact`, `decision`, and `preference`.
"""


from datetime import datetime


def _get_connection():
    """
    Open and initialise a connection to ALF's shared memory database.

    The connection helper lives in ``alf.memory`` and is imported lazily
    to avoid an import cycle.

    Returns:
        An initialised SQLite database connection.
    """

    from .memory import get_connection

    return get_connection()


def create_tables(connection):
    """Create the memory category schema."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY (parent_id)
                REFERENCES memory_categories(id)
                ON DELETE SET NULL
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            memory_categories_parent_name
        ON memory_categories (
            COALESCE(parent_id, 0),
            name
        )
        """
    )


def migrate_from_v7(connection):
    """Migrate the memory database from schema version 7 to 8."""

    create_tables(connection)

    columns = connection.execute(
        "PRAGMA table_info(memories)"
    ).fetchall()

    column_names = {column[1] for column in columns}

    if "memory_category_id" not in column_names:
        connection.execute(
            """
            ALTER TABLE memories
            ADD COLUMN memory_category_id INTEGER
            REFERENCES memory_categories(id)
            """
        )


def create_memory_category(name: str, parent_id=None):
    """
    Create a new memory category.

    Category names must be unique among siblings. A category's position
    is assigned after the existing siblings.

    Returns:
        The ID of the new category, or ``"duplicate"`` when the name is
        already used by a sibling.
    """

    with _get_connection() as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM memory_categories
            WHERE COALESCE(parent_id, 0) = COALESCE(?, 0)
              AND name = ?
            """,
            (parent_id, name),
        ).fetchone()

        if duplicate is not None:
            return "duplicate"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        position = connection.execute(
            """
            SELECT COALESCE(MAX(position), -1) + 1
            FROM memory_categories
            WHERE COALESCE(parent_id, 0) = COALESCE(?, 0)
            """,
            (parent_id,),
        ).fetchone()[0]

        cursor = connection.execute(
            """
            INSERT INTO memory_categories (
                name,
                parent_id,
                status,
                created,
                modified,
                position
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                parent_id,
                "active",
                now,
                now,
                position,
            ),
        )

        return cursor.lastrowid


def get_memory_categories():
    """
    Return all memory categories in hierarchical position order.

    Returns:
        A list of category dictionaries.
    """

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, parent_id, status, created, modified, position
            FROM memory_categories
            ORDER BY COALESCE(parent_id, 0), position
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "parent_id": row[2],
            "status": row[3],
            "created": row[4],
            "modified": row[5],
            "position": row[6],
        }
        for row in rows
    ]


def get_memory_category(category_id):
    """
    Return a memory category by ID.

    Args:
        category_id: ID of the memory category.

    Returns:
        A category dictionary, or ``None`` when the category does not exist.
    """
    with _get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, parent_id, status, created, modified, position
            FROM memory_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "parent_id": row[2],
        "status": row[3],
        "created": row[4],
        "modified": row[5],
        "position": row[6],
    }


def update_memory_category(category_id, name):
    """
    Rename a memory category.

    Returns:
        ``"duplicate"`` when the name is already used by a sibling,
        ``False`` when the category does not exist, otherwise ``True``.
    """

    with _get_connection() as connection:
        category = connection.execute(
            """
            SELECT parent_id
            FROM memory_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

        if category is None:
            return False

        duplicate = connection.execute(
            """
            SELECT id
            FROM memory_categories
            WHERE COALESCE(parent_id, 0) = COALESCE(?, 0)
              AND name = ?
              AND id != ?
            """,
            (category[0], name, category_id),
        ).fetchone()

        if duplicate is not None:
            return "duplicate"

        modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        connection.execute(
            """
            UPDATE memory_categories
            SET name = ?, modified = ?
            WHERE id = ?
            """,
            (name, modified, category_id),
        )

    return True


def delete_memory_category(category_id):
    """
    Delete a memory category.

    Memories assigned to the category become unclassified. Child
    categories become top-level categories through the foreign key's
    ON DELETE SET NULL behaviour.

    Returns:
        ``False`` when the category does not exist, otherwise ``True``.
    """

    with _get_connection() as connection:
        category = connection.execute(
            """
            SELECT id
            FROM memory_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

        if category is None:
            return False

        connection.execute(
            """
            UPDATE memories
            SET memory_category_id = NULL
            WHERE memory_category_id = ?
            """,
            (category_id,),
        )

        connection.execute(
            """
            DELETE FROM memory_categories
            WHERE id = ?
            """,
            (category_id,),
        )

    return True
