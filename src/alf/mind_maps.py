"""
ALF's mind map persistence data layer.

This module manages the SQLite-backed storage and category management
for ALF's mind maps. It shares ALF's single memory database through
``alf.memory.get_connection``; that import is deferred until call time
so that this module never participates in an import cycle with
``alf.memory``.
"""

from datetime import datetime


def _get_connection():
    """
    Open and initialise a connection to ALF's shared memory database.

    The connection helper lives in ``alf.memory`` and is imported lazily
    to break the import cycle between this module and ``alf.memory``.

    Returns:
        An initialised SQLite database connection.
    """

    from .memory import get_connection

    return get_connection()


def create_tables(connection):
    """
    Create the mind map tables when they do not already exist.

    Args:
        connection: An open SQLite database connection.

    The supplied connection is updated in place and is not committed
    here; the caller owns the transaction and version bookkeeping.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
      CREATE TABLE IF NOT EXISTS mindmap_categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL DEFAULT 'active',
          created TEXT NOT NULL,
          modified TEXT NOT NULL,
          position INTEGER
      )
        """
    )


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mindmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            FOREIGN KEY (category_id)
                REFERENCES mindmap_categories(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mindmap_documents (
            mindmap_id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            FOREIGN KEY (mindmap_id)
                REFERENCES mindmaps(id)
                ON DELETE CASCADE
        )
        """
    )


def migrate_from_v4(connection):
    """
    Rebuild the mind map schema for databases at schema version 4.

    Legacy ``mindmaps`` rows carrying a text ``category`` and ``project``
    are migrated to the current ``category_id``-based shape.

    Args:
        connection: An open SQLite database connection.

    The supplied connection is updated in place and is not committed
    here; the caller owns the transaction and version bookkeeping.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = connection.cursor()

    categories = cursor.execute(
        """
        SELECT DISTINCT category
        FROM mindmaps
        """
    ).fetchall()

    for (category_name,) in categories:
        cursor.execute(
            """
            INSERT OR IGNORE INTO mindmap_categories (
                name,
                status,
                created,
                modified
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                category_name,
                "active",
                now,
                now,
            ),
        )

    cursor.execute(
        """
        ALTER TABLE mindmap_documents
        RENAME TO mindmap_documents_v4
        """
    )

    cursor.execute(
        """
        ALTER TABLE mindmaps
        RENAME TO mindmaps_v4
        """
    )

    cursor.execute(
        """
        CREATE TABLE mindmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            FOREIGN KEY (category_id)
                REFERENCES mindmap_categories(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
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

    cursor.execute(
        """
        INSERT INTO mindmaps (
            id,
            category_id,
            name,
            status,
            created,
            modified
        )
        SELECT
            m.id,
            c.id,
            m.project,
            m.status,
            m.created,
            m.modified
        FROM mindmaps_v4 AS m
        JOIN mindmap_categories AS c
            ON c.name = m.category
        """
    )

    cursor.execute(
        """
        INSERT INTO mindmap_documents (
            mindmap_id,
            content
        )
        SELECT
            mindmap_id,
            content
        FROM mindmap_documents_v4
        """
    )

    cursor.execute(
        """
        DROP TABLE mindmap_documents_v4
        """
    )

    cursor.execute(
        """
        DROP TABLE mindmaps_v4
        """
    )


def migrate_position_v5(connection):
    """
    Add and seed the mind map category ordering for databases at
    schema version 5.

    Args:
        connection: An open SQLite database connection.

    The supplied connection is updated in place and is not committed
    here; the caller owns the transaction and version bookkeeping.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        ALTER TABLE mindmap_categories
        ADD COLUMN position INTEGER
        """
    )

    categories = cursor.execute(
        """
        SELECT id, name
        FROM mindmap_categories
        ORDER BY
            CASE WHEN name = 'Uncategorised' THEN 0 ELSE 1 END,
            name
        """
    ).fetchall()

    for position, (category_id, _) in enumerate(categories):
        cursor.execute(
            """
            UPDATE mindmap_categories
            SET position = ?
            WHERE id = ?
            """,
            (position, category_id),
        )


def _create_uncategorised(connection) -> int:
    """
    Insert the reserved ``Uncategorised`` category at position 0.

    Existing categories are shifted up by one position so that
    ``Uncategorised`` claims position 0 regardless of when it is created.

    Returns:
        The ID of the newly created category.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection.execute(
        """
        UPDATE mindmap_categories
        SET position = position + 1
        WHERE position >= 0
        """
    )

    cursor = connection.execute(
        """
        INSERT INTO mindmap_categories (
            name,
            status,
            created,
            modified,
            position
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Uncategorised", "active", now, now, 0),
    )

    return cursor.lastrowid


def create_mindmap_category(name: str):
    """
    Create a new mind map category.

    The reserved ``Uncategorised`` category is always placed at position 0.

    Args:
        name: The category name.

    Returns:
        The ID of the newly created category, or ``"duplicate"`` when a
        category with the given name already exists.
    """

    with _get_connection() as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = ?
            """,
            (name,),
        ).fetchone()

        if duplicate is not None:
            return "duplicate"

        if name == "Uncategorised":
            return _create_uncategorised(connection)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = connection.cursor()

        position = cursor.execute(
            """
            SELECT COALESCE(MAX(position), -1) + 1
            FROM mindmap_categories
            """
        ).fetchone()[0]

        cursor.execute(
            """
            INSERT INTO mindmap_categories (
                name,
                status,
                created,
                modified,
                position
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                "active",
                now,
                now,
                position,
            ),
        )

        return cursor.lastrowid


def get_mindmap_categories():
    """
    Return all mind map categories in their stored position order.

    Returns:
        A list of category dictionaries.
    """

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, status, created, modified, position
            FROM mindmap_categories
            ORDER BY position
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "status": row[2],
            "created": row[3],
            "modified": row[4],
            "position": row[5],
        }
        for row in rows
    ]


def move_mindmap_category(category_id: int, position: int):
    """
    Move a mind map category to a new position.

    Args:
        category_id: The ID of the category to move.
        position: The zero-based destination position.

    Returns:
        ``True`` when the category is moved, otherwise ``False``.
    """

    with _get_connection() as connection:
        category = connection.execute(
            """
            SELECT name, position
            FROM mindmap_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

        if category is None:
            return False

        category_name = category[0]
        current_position = category[1]

        if category_name == "Uncategorised":
            return True

        uncategorised = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = 'Uncategorised'
            """
        ).fetchone()

        if uncategorised is not None:
            position = max(position, 1)

        if current_position == position:
            return True

        if position < current_position:
            connection.execute(
                """
                UPDATE mindmap_categories
                SET position = position + 1
                WHERE position >= ?
                  AND position < ?
                """,
                (position, current_position),
            )
        else:
            connection.execute(
                """
                UPDATE mindmap_categories
                SET position = position - 1
                WHERE position > ?
                  AND position <= ?
                """,
                (current_position, position),
            )

        connection.execute(
            """
            UPDATE mindmap_categories
            SET position = ?
            WHERE id = ?
            """,
            (position, category_id),
        )

    return True


def update_mindmap_category(
    category_id: int,
    name: str,
):
    """
    Rename an existing mind map category.

    Categories have no status lifecycle; they are either present or
    deleted. Their status is always ``"active"``.

    Returns:
        ``True`` when the category is renamed, ``False`` when no category
        with the given id exists or when the reserved ``"Uncategorised"``
        category itself is renamed, and ``"duplicate"`` when ``name`` is
        already used by another category or is the reserved
        ``"Uncategorised"`` name.
    """

    with _get_connection() as connection:
        category = connection.execute(
            """
            SELECT id, name
            FROM mindmap_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

        if category is None:
            return False

        if category[1] == "Uncategorised":
            return False

        if name == "Uncategorised":
            return "duplicate"

        duplicate = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = ? AND id != ?
            """,
            (name, category_id),
        ).fetchone()

        if duplicate is not None:
            return "duplicate"

        modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        connection.execute(
            """
            UPDATE mindmap_categories
            SET name = ?,
                modified = ?
            WHERE id = ?
            """,
            (
                name,
                modified,
                category_id,
            ),
        )

    return True


def delete_mindmap_category(category_id: int):
    """
    Delete an existing mind map category.

    Mind maps belonging to the category are moved to
    ``Uncategorised`` before the category is deleted. The remaining
    categories are then renumbered sequentially from position 0 in
    their existing order.

    Returns:
        ``True`` when the category is deleted, otherwise ``False``.
    """

    with _get_connection() as connection:
        category = connection.execute(
            """
            SELECT id, name
            FROM mindmap_categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()

        if category is None:
            return False

        uncategorised = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = 'Uncategorised'
            """,
        ).fetchone()

        if uncategorised is None:
            uncategorised = (_create_uncategorised(connection),)

        if category[1] == "Uncategorised":
            return False

        connection.execute(
            """
            UPDATE mindmaps
            SET category_id = ?
            WHERE category_id = ?
            """,
            (
                uncategorised[0],
                category_id,
            ),
        )

        connection.execute(
            """
            DELETE FROM mindmap_categories
            WHERE id = ?
            """,
            (category_id,),
        )

        remaining = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            ORDER BY position
            """
        ).fetchall()

        for new_position, row in enumerate(remaining):
            connection.execute(
                """
                UPDATE mindmap_categories
                SET position = ?
                WHERE id = ?
                """,
                (new_position, row[0]),
            )

    return True


def create_mindmap(category: str, name: str, content: str):
    """
    Create a new mind map and its associated document.

    Returns:
        The new mind map ID.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_connection() as connection:
        cursor = connection.cursor()

        category_row = cursor.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = ?
            """,
            (category,),
        ).fetchone()

        if category_row is None:
            if category == "Uncategorised":
                category_id = _create_uncategorised(connection)
            else:
                position = cursor.execute(
                    """
                    SELECT COALESCE(MAX(position), -1) + 1
                    FROM mindmap_categories
                    """
                ).fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO mindmap_categories (
                        name,
                        status,
                        created,
                        modified,
                        position
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        "active",
                        now,
                        now,
                        position,
                    ),
                )
                category_id = cursor.lastrowid
        else:
            category_id = category_row[0]

        cursor.execute(
            """
            INSERT INTO mindmaps (
                category_id,
                name,
                status,
                created,
                modified
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                category_id,
                name,
                "active",
                now,
                now,
            ),
        )

        mindmap_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO mindmap_documents (
                mindmap_id,
                content
            )
            VALUES (?, ?)
            """,
            (mindmap_id, content),
        )

    return mindmap_id


def get_mindmap(mindmap_id: int):
    """
    Retrieve a mind map and its associated document.

    Returns:
        The mind map as a dictionary, or ``None`` if it does not exist.
    """

    with _get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                m.id,
                c.name,
                m.name,
                m.status,
                m.created,
                m.modified,
                d.content
            FROM mindmaps AS m
            JOIN mindmap_categories AS c
                ON c.id = m.category_id
            JOIN mindmap_documents AS d
                ON d.mindmap_id = m.id
            WHERE m.id = ?
            """,
            (mindmap_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "category": row[1],
        "name": row[2],
        "status": row[3],
        "created": row[4],
        "modified": row[5],
        "content": row[6],
    }


def get_mindmaps():
    """
    Retrieve all mind maps.

    Returns:
        A list of mind maps ordered by ID.
    """

    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                m.id,
                c.name,
                m.name,
                m.status,
                m.created,
                m.modified,
                d.content
            FROM mindmaps AS m
            JOIN mindmap_categories AS c
                ON c.id = m.category_id
            JOIN mindmap_documents AS d
                ON d.mindmap_id = m.id
            WHERE m.status = 'active'
            ORDER BY m.id
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "category": row[1],
            "name": row[2],
            "status": row[3],
            "created": row[4],
            "modified": row[5],
            "content": row[6],
        }
        for row in rows
    ]


def update_mindmap(
    mindmap_id: int,
    category: str,
    name: str,
    status: str,
    content: str,
):
    """
    Update a mind map and its associated document.

    The modified timestamp is refreshed whenever the mind map is
    updated.

    Returns:
        ``True`` when the mind map is updated, otherwise ``False`` when
        the mind map does not exist.
    """

    with _get_connection() as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM mindmaps
            WHERE id = ?
            """,
            (mindmap_id,),
        ).fetchone()

        if existing is None:
            return False

        category_row = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = ?
            """,
            (category,),
        ).fetchone()

        if category_row is None:
            return False

        modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        connection.execute(
            """
            UPDATE mindmaps
            SET category_id = ?,
                name = ?,
                status = ?,
                modified = ?
            WHERE id = ?
            """,
            (
                category_row[0],
                name,
                status,
                modified,
                mindmap_id,
            ),
        )

        connection.execute(
            """
            UPDATE mindmap_documents
            SET content = ?
            WHERE mindmap_id = ?
            """,
            (content, mindmap_id),
        )

    return True


def move_mindmap(mindmap_id: int, category: str):
    """
    Move a mind map to a different category.

    Returns:
        ``True`` when the mind map is moved, otherwise ``False`` when
        the mind map or category does not exist.
    """

    with _get_connection() as connection:
        category_row = connection.execute(
            """
            SELECT id
            FROM mindmap_categories
            WHERE name = ?
            """,
            (category,),
        ).fetchone()

        if category_row is None:
            return False

        result = connection.execute(
            """
            UPDATE mindmaps
            SET category_id = ?,
                modified = ?
            WHERE id = ?
            """,
            (
                category_row[0],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                mindmap_id,
            ),
        )

    return result.rowcount > 0


def delete_mindmap(mindmap_id: int):
    """
    Permanently delete a mind map and its associated document.

    Returns:
        ``True`` when the mind map is deleted, otherwise ``False``
        when it does not exist.
    """

    with _get_connection() as connection:
        result = connection.execute(
            """
            DELETE FROM mindmaps
            WHERE id = ?
            """,
            (mindmap_id,),
        )

    return result.rowcount > 0
