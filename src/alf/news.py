"""
ALF's news data layer.

This module manages ALF's subscribed news subjects. Subscriptions are
stored durably in the shared SQLite database while Miniflux retains the
feed retrieval and long-lived item store; ALF owns the news domain and
treats Miniflux as infrastructure.

Items are identified by an entry hash derived from their URL and
publication time rather than by Miniflux's numeric entry id, so ALF
keeps a stable view of the items it has imported even when Miniflux
purges archived entries and reuses their identifiers.

Presentation and command-handling concerns remain outside this module;
its responsibility is to provide the news data and news-system
information to the rest of ALF.
"""

import hashlib
import os
import re
import sqlite3
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .miniflux import Miniflux, MinifluxError
from .news_intent import NewsIntent, normalize_text
from .paths import get_data_directory

CONFIG = get_data_directory() / "news.toml"

NEWS_QUERY_LIMIT = 25


class NewsError(Exception):
    """
    Raised when a news operation cannot be completed.
    """


@dataclass(frozen=True)
class NewsQuery:
    """
    A News retrieval query over ALF's stored news items.

    Items are matched by topic terms against their title and summary, by
    subject alignment against ALF's stored news subjects, and by an
    inclusive publication window. Results are returned newest first.

    Attributes:
        topics: Significant topic terms to match against item text.
        subject: A subject name to restrict results to, or ``None``.
        start: Inclusive window start, or ``None`` for no lower bound.
        end: Inclusive window end, or ``None`` for no upper bound.
        limit: Maximum number of items to return, between 1 and 100.
    """

    topics: tuple[str, ...] = ()
    subject: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 25

    @classmethod
    def from_intent(cls, intent: NewsIntent):
        """
        Build a query from a deterministically interpreted News question.

        Args:
            intent: A ``NewsIntent`` describing the question's topics
                and window.

        Returns:
            A ``NewsQuery`` for the intent's topics and window.
        """

        return cls(
            topics=intent.topics,
            start=intent.window.start,
            end=intent.window.end,
        )


def create_tables(connection):
    """
    Create the news schema in an open SQLite connection.

    The news tables were added in schema version 7. They are created in
    place and the caller owns the surrounding transaction and version
    bookkeeping, mirroring the memory and mind map tables.

    Args:
        connection: An open SQLite database connection.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_subjects (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL UNIQUE,
            created TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_feeds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id       INTEGER NOT NULL,
            miniflux_feed_id INTEGER NOT NULL,
            feed_url         TEXT NOT NULL,
            title            TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id    INTEGER NOT NULL,
            feed_id       INTEGER NOT NULL,
            entry_hash    TEXT NOT NULL,
            title         TEXT NOT NULL,
            url           TEXT NOT NULL,
            summary       TEXT,
            published_at  TEXT NOT NULL,
            first_seen_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS news_items_entry_idx
        ON news_items (subject_id, entry_hash)
        """
    )


def get_news_config():
    """
    Return the Miniflux service configuration, or ``None`` when the news
    service has not been configured.
    """

    if not CONFIG.exists():
        return None

    with open(CONFIG, "rb") as config_file:
        return tomllib.load(config_file)


def save_news_config(base_url, api_key):
    """
    Write the Miniflux service configuration.

    The configuration file is private to the current user.

    Args:
        base_url: The Miniflux service base URL.
        api_key: The Miniflux API key.
    """

    CONFIG.parent.mkdir(parents=True, exist_ok=True)

    CONFIG.write_text(
        f'base_url = "{base_url}"\n'
        f'api_key = "{api_key}"\n'
    )

    os.chmod(CONFIG, 0o600)

    return True


def initialise(base_url, api_key, client=None):
    """
    Configure the Miniflux service after verifying it is reachable.

    Args:
        base_url: The Miniflux service base URL.
        api_key: The Miniflux API key.
        client: An optional Miniflux client to use for the connection
            check.

    Returns:
        ``True`` when the configuration was saved.
    """

    client = client or Miniflux(base_url, api_key)

    client.me()

    return save_news_config(base_url, api_key)


def get_client():
    """
    Build a Miniflux client from the news configuration.

    Returns:
        A configured Miniflux client.

    Raises:
        NewsError: When the news service has not been configured.
    """

    config = get_news_config()

    if config is None:
        raise NewsError("News is not configured. Run `alf news init`.")

    return Miniflux(
        config["base_url"],
        config["api_key"],
    )


def add_subject(name, feed_urls, client=None):
    """
    Register a news subject and its feed subscriptions.

    The subject is mirrored as a Miniflux category so its entries can be
    retrieved as one set. Feeds that are already subscribed are reported
    without being duplicated.

    Args:
        name: The subject name.
        feed_urls: Feed URLs to subscribe for the subject.
        client: An optional Miniflux client.

    Returns:
        A dictionary summarising the subject and its feeds.
    """

    name = name.strip()

    if not name:
        raise NewsError("A news subject name is required.")

    feed_urls = [
        feed_url.strip()
        for feed_url in feed_urls
        if feed_url.strip()
    ]

    if not feed_urls:
        raise NewsError("At least one feed URL is required.")

    client = client or get_client()

    with _get_connection() as connection:
        subject = _ensure_subject(connection, name)
        category = _ensure_subject_category(client, name)

        result = {
            "subject": subject["name"],
            "added": [],
            "existing": [],
        }

        for feed_url in feed_urls:
            feed = _ensure_feed(client, category["id"], feed_url)

            if _register_feed(connection, subject["id"], feed):
                result["added"].append(feed_url)
            else:
                result["existing"].append(feed_url)

        return result


def add_feed_to_subject(subject_id, feed_url, client=None):
    """
    Add a feed subscription to an existing news subject.

    Args:
        subject_id: The ALF news subject id.
        feed_url: The feed URL to subscribe.
        client: An optional Miniflux client.

    Returns:
        A dictionary describing the added feed.

    Raises:
        NewsError: If the subject does not exist or the feed URL is empty.
    """

    feed_url = feed_url.strip()

    if not feed_url:
        raise NewsError("A feed URL is required.")

    client = client or get_client()

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name FROM news_subjects WHERE id = ?",
            (subject_id,),
        )

        subject = cursor.fetchone()

        if subject is None:
            raise NewsError("News subject not found.")

        category = _ensure_subject_category(client, subject[1])
        feed = _ensure_feed(client, category["id"], feed_url)

        if not _register_feed(connection, subject[0], feed):
            raise NewsError(
                f"The feed is already subscribed to '{subject[1]}'."
            )

        return {
            "id": feed["id"],
            "title": feed["title"],
            "feed_url": feed["feed_url"],
            "subject_id": subject[0],
            "subject": subject[1],
        }


def move_feed(feed_id, subject_id, client=None):
    """
    Move a news feed subscription to another subject.

    The feed is moved in Miniflux to the destination subject's category
    before ALF's subscription is updated, so a Miniflux failure leaves
    both sides in the original subject.

    Args:
        feed_id: The ALF news feed id.
        subject_id: The destination ALF subject id.
        client: An optional Miniflux client.

    Returns:
        A dictionary describing the moved feed.

    Raises:
        NewsError: If the feed or destination subject does not exist, or
            the feed is already subscribed to the destination subject.
    """

    client = client or get_client()

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, title, subject_id, miniflux_feed_id
            FROM news_feeds
            WHERE id = ?
            """,
            (feed_id,),
        )
        feed = cursor.fetchone()

        if feed is None:
            raise NewsError("News feed not found.")

        cursor.execute(
            "SELECT id, name FROM news_subjects WHERE id = ?",
            (subject_id,),
        )
        subject = cursor.fetchone()

        if subject is None:
            raise NewsError("News subject not found.")

        if feed[2] == subject_id:
            return {
                "id": feed[0],
                "title": feed[1],
                "subject_id": subject[0],
                "subject": subject[1],
            }

        cursor.execute(
            """
            SELECT id FROM news_feeds
            WHERE subject_id = ? AND feed_url = (
                SELECT feed_url FROM news_feeds WHERE id = ?
            )
            """,
            (subject_id, feed_id),
        )

        if cursor.fetchone():
            raise NewsError(
                f"The feed is already subscribed to '{subject[1]}'."
            )

        category = _ensure_subject_category(client, subject[1])

        client.update_feed(feed[3], category["id"])

        cursor.execute(
            "UPDATE news_feeds SET subject_id = ? WHERE id = ?",
            (subject_id, feed_id),
        )

        return {
            "id": feed[0],
            "title": feed[1],
            "subject_id": subject[0],
            "subject": subject[1],
        }


def delete_feed(feed_id, client=None):
    """
    Delete an ALF news feed subscription.

    The corresponding Miniflux feed is also deleted when no other ALF
    subject is subscribed to it.

    Args:
        feed_id: The ALF news feed id.
        client: An optional Miniflux client.

    Returns:
        A dictionary describing the deleted feed.

    Raises:
        NewsError: If the feed does not exist.
    """
    client = client or get_client()

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, title, miniflux_feed_id
            FROM news_feeds
            WHERE id = ?
            """,
            (feed_id,),
        )
        feed = cursor.fetchone()

        if feed is None:
            raise NewsError("News feed not found.")

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM news_feeds
            WHERE miniflux_feed_id = ?
              AND id != ?
            """,
            (feed[2], feed_id),
        )
        remaining = cursor.fetchone()[0]

        cursor.execute(
            "DELETE FROM news_items WHERE feed_id = ?",
            (feed_id,),
        )

        cursor.execute(
            "DELETE FROM news_feeds WHERE id = ?",
            (feed_id,),
        )

        if remaining == 0:
            client.delete_feed(feed[2])

        return {
            "id": feed[0],
            "title": feed[1],
        }


def _sync_subject_feeds(connection, client, subjects, categories):
    """Register Miniflux feeds belonging to existing ALF subjects."""
    for subject in subjects:
        category = categories.get(subject["name"])

        if category is None:
            continue

        for feed in client.get_feeds(category_id=category["id"]):
            _register_feed(connection, subject["id"], feed)


def refresh(subject=None, client=None):
    """
    Refresh stored news feeds and import their entries.

    Miniflux is refreshed first, then the latest read and unread entries
    are retrieved. Entries are deduplicated by entry hash, so refreshing
    repeatedly is safe and imports only items not already stored. Feeds
    that fail to refresh are reported without aborting the whole refresh.

    Args:
        subject: Optional subject name to restrict the refresh to.
        client: An optional Miniflux client.

    Returns:
        A dictionary summarising the refresh.

    Raises:
        NewsError: When no feeds are stored to refresh.
    """

    client = client or get_client()

    with _get_connection() as connection:
        subjects = _subjects_with_feeds(connection, subject)

        if not subjects:
            if subject:
                raise NewsError(
                    f"No feeds are stored for subject '{subject}'."
                )

            raise NewsError(
                "No news feeds are stored. "
                "Add a subject with `alf news add`."
            )

        categories = {
            category["title"]: category
            for category in client.get_categories()
        }

        _sync_subject_feeds(
            connection,
            client,
            subjects,
            categories,
        )

        subjects = _subjects_with_feeds(connection, subject)
        feeds_by_id = {
            feed["id"]: feed
            for feed in client.get_feeds()
        }

        refreshed = 0
        imported = 0
        skipped = 0
        failures = []
        subject_results = []

        for subject_entries in subjects:
            subject_imported = 0

            for feed in subject_entries["feeds"]:
                miniflux_feed = feeds_by_id.get(feed["miniflux_feed_id"])

                if miniflux_feed is not None:
                    connection.execute(
                        """
                        UPDATE news_feeds
                        SET title = ?
                        WHERE id = ?
                        """,
                        (
                            miniflux_feed["title"],
                            feed["id"],
                        ),
                    )

                try:
                    client.refresh_feed(feed["miniflux_feed_id"])
                except MinifluxError as exc:
                    failures.append(
                        {
                            "feed": feed["title"],
                            "reason": str(exc),
                        }
                    )
                    continue

                refreshed += 1

                try:
                    entries = client.get_entries(
                        feed_id=feed["miniflux_feed_id"],
                        limit=100,
                    )
                except MinifluxError as exc:
                    failures.append(
                        {
                            "feed": feed["title"],
                            "reason": str(exc),
                        }
                    )
                    continue

                count, deduplicated = _import_entries(
                    connection,
                    subject_entries["id"],
                    entries,
                )

                imported += count
                skipped += deduplicated
                subject_imported += count

            subject_results.append(
                {
                    "name": subject_entries["name"],
                    "new_items": subject_imported,
                }
            )

        return {
            "subject": subject,
            "refreshed": refreshed,
            "imported": imported,
            "skipped": skipped,
            "failures": failures,
            "subjects": subject_results,
        }


def list_items(subject=None, feed_id=None, days=None, limit=None):
    """
    Return stored news items, newest first.

    Args:
        subject: Optional subject name to restrict the results to.
        feed_id: Optional stored feed id to restrict the results to.
        days: Optional number of days back to include.

    Returns:
        A list of news item dictionaries.
    """

    cutoff = None

    if days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=days)

    with _get_connection() as connection:
        cursor = connection.cursor()

        conditions = []
        parameters = []

        if subject:
            conditions.append("s.name = ?")
            parameters.append(subject)

        if feed_id is not None:
            conditions.append("f.id = ?")
            parameters.append(feed_id)

        query = """
            SELECT
                i.id,
                s.name,
                f.title,
                i.title,
                i.url,
                i.summary,
                i.published_at,
                i.first_seen_at
            FROM news_items i
            JOIN news_feeds f ON f.id = i.feed_id
            JOIN news_subjects s ON s.id = i.subject_id
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        cursor.execute(query, parameters)

        items = []
        rows = cursor.fetchall()

        for row in rows:
            published_at = row[6]
            published = _parse_timestamp(published_at)

            if cutoff is not None and published < cutoff:
                continue

            items.append(
                {
                    "id": row[0],
                    "subject": row[1],
                    "feed_title": row[2],
                    "title": row[3],
                    "url": row[4],
                    "summary": row[5],
                    "published_at": published_at,
                    "first_seen_at": row[7],
                }
            )

    items.sort(
        key=lambda item: _parse_timestamp(item["published_at"]),
        reverse=True,
    )

    if limit is not None:
        if not 1 <= limit <= 100:
            raise NewsError("A news item limit must be between 1 and 100.")

        items = items[:limit]

    return items


def query_items(query):
    """
    Retrieve stored news items matching a news query.

    Matching is confined to items whose stored subject aligns with the
    query's subject, when one is given, and whose title or summary
    contains at least one of the query's topic terms. Items are matched
    against the inclusive publication window and returned newest first,
    up to the query limit.

    Args:
        query: The ``NewsQuery`` describing the retrieval.

    Returns:
        A list of matching news item dictionaries, newest first. Each
        item includes the terms it matched and an empty content slot for
        the presentation layer.

    Raises:
        NewsError: When the query has no topic terms or subject, or its
            limit is outside 1-100.
    """

    if not query.topics and query.subject is None:
        raise NewsError("A news query needs at least one topic or a subject.")

    if not 1 <= query.limit <= 100:
        raise NewsError("A news query limit must be between 1 and 100.")

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name FROM news_subjects ORDER BY name"
        )

        stored_subjects = [
            {"id": row[0], "name": row[1]}
            for row in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT
                i.subject_id,
                i.id,
                s.name,
                f.title,
                i.title,
                i.url,
                i.summary,
                i.published_at,
                i.first_seen_at
            FROM news_items i
            JOIN news_feeds f ON f.id = i.feed_id
            JOIN news_subjects s ON s.id = i.subject_id
            """
        )

        candidates = cursor.fetchall()

    subject_ids = _align_subjects(query.subject, stored_subjects)

    items = []

    for row in candidates:
        subject_id = row[0]

        if subject_ids is not None and subject_id not in subject_ids:
            continue

        published_at = _parse_timestamp(row[7])

        if query.start is not None and published_at < query.start:
            continue

        if query.end is not None and published_at > query.end:
            continue

        item = {
            "id": row[1],
            "subject": row[2],
            "feed_title": row[3],
            "title": row[4],
            "url": row[5],
            "summary": row[6],
            "published_at": row[7],
            "first_seen_at": row[8],
            "matched_terms": [],
            "content": None,
        }

        if query.topics:
            item["matched_terms"] = _match_terms(
                query.topics,
                f"{row[4]} {row[6]}" if row[6] else row[4],
            )

            if not item["matched_terms"]:
                continue

        items.append(item)

    items.sort(
        key=lambda item: _parse_timestamp(item["published_at"]),
        reverse=True,
    )

    return items[: query.limit]


def get_news_feeds():
    """
    Return stored news feeds grouped by subject.

    Returns:
        A list of feed dictionaries, each including its subject name.
    """

    with _get_connection() as connection:
        subjects = _subjects_with_feeds(connection)

    feeds = []

    for subject in subjects:
        for feed in subject["feeds"]:
            feeds.append(
                {
                    "id": feed["id"],
                    "subject": subject["name"],
                    "title": feed["title"],
                }
            )

    return feeds


def list_subjects():
    """
    Return stored news subjects with their feed and item counts.

    Returns:
        A list of subject dictionaries, ordered by subject name.
    """

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                s.id,
                s.name,
                (
                    SELECT COUNT(*)
                    FROM news_feeds f
                    WHERE f.subject_id = s.id
                ),
                (
                    SELECT COUNT(*)
                    FROM news_items i
                    WHERE i.subject_id = s.id
                )
            FROM news_subjects s
            ORDER BY s.name
            """
        )

        return [
            {
                "id": row[0],
                "name": row[1],
                "feeds": row[2],
                "items": row[3],
            }
            for row in cursor.fetchall()
        ]


def get_news_information():
    """
    Return information about ALF's stored news data.

    This never contacts the news service, so it is safe to call from
    ALF's capability discovery.
    """

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name FROM news_subjects ORDER BY name"
        )

        subjects = [
            {"id": row[0], "name": row[1]}
            for row in cursor.fetchall()
        ]

        cursor.execute("SELECT COUNT(*) FROM news_feeds")
        feeds = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM news_items")
        items = cursor.fetchone()[0]

    return {
        "subjects": subjects,
        "feeds": feeds,
        "items": items,
    }


def get_news_status(client=None):
    """
    Return ALF's news state and the reachability of its news service.
    """

    service = {
        "configured": False,
        "reachable": None,
    }

    if get_news_config() is not None:
        service["configured"] = True

        try:
            (client or get_client()).me()
            service["reachable"] = True
        except (MinifluxError, NewsError):
            service["reachable"] = False

    information = get_news_information()

    return {
        **information,
        "service": service,
    }


def get_capability():
    """
    Return news capability information.
    """

    return {
        "id": "news",
        "name": "News",
        "description": "Subscribed news items via Miniflux",
        "details": get_news_information(),
    }


def _get_connection():
    """
    Open a connection to ALF's shared SQLite database.
    """

    from .memory import get_connection

    return get_connection()


def rename_subject(subject_id, name, client=None):
    """
    Rename a stored news subject and its corresponding Miniflux category.

    Args:
        subject_id: The ALF subject id.
        name: The new subject name.
        client: An optional Miniflux client.

    Returns:
        A dictionary describing the renamed subject.

    Raises:
        NewsError: If the subject does not exist or the name is invalid.
    """

    name = name.strip()

    if not name:
        raise NewsError("A news subject name is required.")

    client = client or get_client()

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name FROM news_subjects WHERE id = ?",
            (subject_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise NewsError("News subject not found.")

        old_name = row[1]

        cursor.execute(
            "SELECT id FROM news_subjects WHERE name = ? AND id != ?",
            (name, subject_id),
        )

        if cursor.fetchone():
            raise NewsError(
                f"A news subject named '{name}' already exists."
            )

        category = None

        for candidate in client.get_categories():
            if candidate["title"] == old_name:
                category = candidate
                break

        if category is None:
            raise NewsError(
                f"Miniflux category '{old_name}' could not be found."
            )

        client.update_category(category["id"], name)

        cursor.execute(
            "UPDATE news_subjects SET name = ? WHERE id = ?",
            (name, subject_id),
        )

        return {
            "id": subject_id,
            "name": name,
        }


def delete_subject(subject_id, client=None):
    """
    Delete a stored news subject and its ALF-side data.

    The corresponding Miniflux category is deleted first, removing its
    feeds and entries through Miniflux's category cascade. A Miniflux
    failure leaves ALF's records intact.

    Args:
        subject_id: The ALF subject id.
        client: An optional Miniflux client.

    Returns:
        A dictionary describing the deleted subject.

    Raises:
        NewsError: If the subject does not exist, or if its Miniflux
            category could not be found or deleted.
    """

    client = client or get_client()

    with _get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name FROM news_subjects WHERE id = ?",
            (subject_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise NewsError("News subject not found.")

        subject_name = row[1]

        category = None

        for candidate in client.get_categories():
            if candidate["title"] == subject_name:
                category = candidate
                break

        if category is None:
            raise NewsError(
                f"Miniflux category '{subject_name}' could not be found."
            )

        client.delete_category(category["id"])

        cursor.execute(
            "DELETE FROM news_items WHERE subject_id = ?",
            (subject_id,),
        )

        cursor.execute(
            "DELETE FROM news_feeds WHERE subject_id = ?",
            (subject_id,),
        )

        cursor.execute(
            "DELETE FROM news_subjects WHERE id = ?",
            (subject_id,),
        )

        return {
            "id": subject_id,
            "name": subject_name,
        }


def _ensure_subject(connection, name):
    """
    Return the subject row for ``name``, creating it when missing.
    """

    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, name, created FROM news_subjects WHERE name = ?",
        (name,),
    )

    row = cursor.fetchone()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "created": row[2],
        }

    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "INSERT INTO news_subjects (name, created) VALUES (?, ?)",
        (name, created),
    )

    return {
        "id": cursor.lastrowid,
        "name": name,
        "created": created,
    }


def _ensure_subject_category(client, name):
    """
    Return the Miniflux category mirroring a subject, creating it when
    missing.
    """

    for category in client.get_categories():
        if category["title"] == name:
            return category

    return client.create_category(name)


def _ensure_feed(client, category_id, feed_url):
    """
    Return the Miniflux feed for ``feed_url``, creating it when missing.
    """

    for feed in client.get_feeds(category_id=category_id):
        if feed["feed_url"] == feed_url:
            return feed

    return client.create_feed(feed_url, category_id)


def _register_feed(connection, subject_id, feed):
    """
    Record a feed subscription for a subject.

    Returns:
        ``True`` when the subscription was newly recorded; ``False`` when
        the subject already subscribed to the feed.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id FROM news_feeds
        WHERE subject_id = ? AND feed_url = ?
        """,
        (subject_id, feed["feed_url"]),
    )

    if cursor.fetchone():
        return False

    cursor.execute(
        """
        INSERT INTO news_feeds
            (subject_id, miniflux_feed_id, feed_url, title)
        VALUES (?, ?, ?, ?)
        """,
        (
            subject_id,
            feed["id"],
            feed["feed_url"],
            feed["title"],
        ),
    )

    return True


def _subjects_with_feeds(connection, subject=None):
    """
    Return stored subjects with their feed subscriptions.
    """

    cursor = connection.cursor()

    conditions = []
    parameters = []

    if subject:
        conditions.append("s.name = ?")
        parameters.append(subject)

    query = """
        SELECT s.id, s.name, f.id, f.miniflux_feed_id, f.title
        FROM news_subjects s
        JOIN news_feeds f ON f.subject_id = s.id
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY s.name, f.id"

    cursor.execute(query, parameters)

    subjects = {}

    for (
        subject_id,
        name,
        feed_id,
        miniflux_feed_id,
        feed_title,
    ) in cursor.fetchall():
        if subject_id not in subjects:
            subjects[subject_id] = {
                "id": subject_id,
                "name": name,
                "feeds": [],
            }

        subjects[subject_id]["feeds"].append(
            {
                "id": feed_id,
                "miniflux_feed_id": miniflux_feed_id,
                "title": feed_title,
            }
        )

    return list(subjects.values())


def _import_entries(connection, subject_id, entries):
    """
    Store entries that are not already stored for the subject.

    Entries are matched to the subject's registered feeds by their
    Miniflux feed id, and deduplicated by entry hash. Items whose feed is
    not registered for the subject are ignored.

    Returns:
        A ``(imported, skipped)`` tuple with the number of newly stored
        items and the number of known items skipped.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT miniflux_feed_id, id FROM news_feeds
        WHERE subject_id = ?
        """,
        (subject_id,),
    )

    feed_ids = dict(cursor.fetchall())

    first_seen_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    imported = 0
    skipped = 0

    for entry in entries:
        feed_id = feed_ids.get(entry.get("feed_id"))

        if feed_id is None:
            continue

        try:
            cursor.execute(
                """
                INSERT INTO news_items (
                    subject_id,
                    feed_id,
                    entry_hash,
                    title,
                    url,
                    summary,
                    published_at,
                    first_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subject_id,
                    feed_id,
                    _entry_hash(
                        entry["url"],
                        entry["published_at"],
                    ),
                    entry["title"],
                    entry["url"],
                    entry.get("summary"),
                    entry["published_at"],
                    first_seen_at,
                ),
            )
        except sqlite3.IntegrityError:
            skipped += 1
        else:
            imported += 1

    return imported, skipped


def _entry_hash(url, published_at):
    """
    Return the durable identity hash for an item.
    """

    return hashlib.sha1(
        f"{url}|{published_at}".encode()
    ).hexdigest()


def _align_subjects(subject_name, subjects):
    """
    Resolve a query subject against ALF's stored news subjects.

    A subject aligns with a stored subject by normalised equality, by
    substring match in either direction, or when any of its words
    appears in the stored subject name.

    Args:
        subject_name: The query's subject name, or ``None`` when the
            query is not restricted to a subject.
        subjects: The stored news subjects as ``id``/``name`` dicts.

    Returns:
        The set of aligned subject ids, or ``None`` when the query is
        not subject-restricted.
    """

    if subject_name is None:
        return None

    normalized = normalize_text(subject_name)
    tokens = normalized.split()

    matches = set()

    for subject in subjects:
        name = normalize_text(subject["name"])

        if (
            normalized == name
            or normalized in name
            or name in normalized
            or any(token in name for token in tokens)
        ):
            matches.add(subject["id"])

    return matches


def _match_terms(topics, text):
    """
    Return the topic terms matching an item's text.

    Matching uses whole-word, case-insensitive searches over the
    normalised item text.

    Returns:
        The terms from ``topics`` that appear in ``text``.
    """

    normalized = normalize_text(text)

    return [
        term
        for term in topics
        if re.search(rf"\b{re.escape(term)}\b", normalized)
    ]


def _parse_timestamp(timestamp):
    """
    Parse an RFC 3339 timestamp used by Miniflux into a datetime.
    """

    return datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )
