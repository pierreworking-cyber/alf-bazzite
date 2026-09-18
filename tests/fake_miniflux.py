"""
In-memory fake of the Miniflux service for ALF tests.

``FakeMiniflux`` implements the small subset of the Miniflux REST API
that ALF's Miniflux client boundary uses, backed by deterministic
in-memory state. Tests drive the real ``alf.miniflux.Miniflux`` client
against the fake through ``FakeMiniflux.transport()``, so request
construction, authentication, and response parsing are exercised
without a network, a container, or a running Miniflux instance.

The fake models Miniflux's refresh behaviour: entries are scheduled per
feed and are emitted with fresh sequential ids when the feed is
refreshed, exactly once each. This makes it deterministic for the
refresh/idempotency and entry-retrieval tests that the upcoming News
domain tests will rely on.
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit


def _timestamp(value):
    """Format a unix timestamp as the RFC 3339 string Miniflux returns."""
    return datetime.fromtimestamp(value, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_time(value):
    """Convert a Miniflux RFC 3339 time string back to a unix timestamp."""
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).timestamp()


def _as_int(value):
    """Convert a query parameter to an integer, tolerating junk."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_entry(entry_id, feed_id, feed_data, source):
    """Build a Miniflux-style entry dictionary from a scheduled source."""
    published_at = source.get("published_at", 0)
    created_at = source.get("created_at", published_at)

    return {
        "id": entry_id,
        "feed_id": feed_id,
        "status": source.get("status", "unread"),
        "title": source.get("title", ""),
        "url": source.get("url", ""),
        "comments_url": "",
        "author": source.get("author", ""),
        "language": source.get("language", ""),
        "content": source.get("content", ""),
        "summary": source.get("summary", ""),
        "hash": source.get(
            "hash",
            hashlib.sha256(
                source.get("url", "").encode("utf-8")
            ).hexdigest(),
        ),
        "published_at": _timestamp(published_at),
        "created_at": _timestamp(created_at),
        "changed_at": _timestamp(source.get("changed_at", 0)),
        "starred": source.get("starred", False),
        "reading_time": 1,
        "tags": source.get("tags", []),
        "enclosures": source.get("enclosures", []),
        "feed": feed_data,
    }


class FakeMiniflux:
    """
    A deterministic, in-memory Miniflux for ALF tests.

    Tests seed state with ``add_category`` and ``add_feed``, schedule
    entries with ``schedule_entries``, and drive the real ``Miniflux``
    client through ``transport()``. Each request is recorded in
    ``requests`` for assertions.
    """

    def __init__(self, version="2.3.3", api_key="test-api-key"):
        self.version = version
        self.api_key = api_key
        self.requests = []
        self._next_category_id = 1
        self._next_feed_id = 1
        self._next_entry_id = 1
        self._categories = []
        self._feeds = []
        self._entries = []
        self._scheduled = {}

    def add_category(self, title):
        """Add a category directly and return it."""
        category = {
            "id": self._next_category_id,
            "title": title,
            "user_id": 1,
            "feed_count": 0,
        }
        self._next_category_id += 1
        self._categories.append(category)

        return dict(category)

    def _remove_category(self, category_id):
        """Remove a category, cascading to its feeds and their entries."""
        feed_ids = {
            feed["id"]
            for feed in self._feeds
            if feed["category_id"] == category_id
        }

        self._feeds = [
            feed
            for feed in self._feeds
            if feed["category_id"] != category_id
        ]

        self._entries = [
            entry
            for entry in self._entries
            if entry["feed_id"] not in feed_ids
        ]

        self._categories = [
            category
            for category in self._categories
            if category["id"] != category_id
        ]

    def add_feed(self, title, feed_url, category_id=None, entries=None):
        """Add a feed directly, optionally scheduling entries for it."""
        if category_id is None:
            category_id = (
                self._categories[0]["id"] if self._categories else 1
            )

        feed = self._register_feed(title, feed_url, category_id)

        if entries:
            self.schedule_entries(feed["id"], entries)

        return feed

    def schedule_entries(self, feed_id, entries):
        """
        Schedule entries to be emitted the next time a feed is refreshed.

        Each scheduled entry is emitted exactly once: a second refresh
        without new scheduling emits nothing. A list of sources is a
        stable per-feed queue, so a feed is never refreshed into
        duplicates.
        """
        self._scheduled.setdefault(feed_id, []).extend(
            [dict(entry) for entry in entries]
        )

    def purge_entries(self):
        """
        Model Miniflux archive purging: entries are removed and their
        sequential ids become available for reuse.
        """
        self._entries = []
        self._next_entry_id = 1

    def transport(self):
        """
        Return a transport matching ``alf.miniflux.Miniflux``'s contract.

        The returned callable routes a client's request into this fake,
        returning a ``(status, body)`` tuple with an encoded JSON body.
        """
        def request(method, url, headers, payload, timeout):
            parts = urlsplit(url)
            query = parse_qs(parts.query)

            status, body = self.handle(
                method,
                parts.path,
                query,
                headers,
                payload,
            )

            if body is None:
                return status, b""

            return status, json.dumps(body).encode("utf-8")

        return request

    def handle(self, method, path, query=None, headers=None, payload=None):
        """
        Process one request and return an ``(status, body)`` pair.

        ``query`` is a mapping of query parameter to string value(s),
        matching the shape produced by ``parse_qs``. Requests without a
        matching ``X-Auth-Token`` are rejected with 401.
        """
        query = {
            key: value[0] if len(value) == 1 else value
            for key, value in (query or {}).items()
        }
        headers = headers or {}
        payload = payload or {}

        self.requests.append(
            {
                "method": method,
                "path": path,
                "query": dict(query),
                "headers": dict(headers),
                "payload": dict(payload),
            }
        )

        if headers.get("X-Auth-Token") != self.api_key:
            return 401, {"error_message": "Authentication failure"}

        if method == "GET" and path == "/v1/version":
            return 200, {"version": self.version}

        if method == "GET" and path == "/v1/me":
            return 200, {"id": 1, "username": "alf"}

        if method == "GET" and path == "/v1/categories":
            return 200, [
                dict(category) for category in self._categories
            ]

        if method == "POST" and path == "/v1/categories":
            title = payload.get("title")

            if not title:
                return 400, {"error_message": "title is required"}

            return 201, self.add_category(title)

        match = re.fullmatch(r"/v1/categories/(\d+)", path)

        if method == "DELETE" and match:
            category_id = int(match.group(1))

            category = next(
                (
                    category
                    for category in self._categories
                    if category["id"] == category_id
                ),
                None,
            )

            if category is None:
                return 404, {"error_message": "Category not found"}

            self._remove_category(category_id)

            return 204, None

        if method == "GET" and path == "/v1/feeds":
            return 200, [dict(feed) for feed in self._feeds]

        match = re.fullmatch(r"/v1/categories/(\d+)/feeds", path)

        if method == "GET" and match:
            category_id = int(match.group(1))
            feeds = [
                dict(feed)
                for feed in self._feeds
                if feed["category_id"] == category_id
            ]

            return 200, feeds

        if method == "POST" and path == "/v1/feeds":
            feed_url = payload.get("feed_url")

            if not feed_url:
                return 400, {"error_message": "feed_url is required"}

            if any(
                feed["feed_url"] == feed_url for feed in self._feeds
            ):
                return 404, {
                    "error_message": "This feed already exists",
                }

            category_id = payload.get("category_id")

            if category_id is not None and not any(
                category["id"] == category_id
                for category in self._categories
            ):
                return 400, {"error_message": "category not found"}

            title = payload.get("title") or feed_url

            feed = self._register_feed(
                title,
                feed_url,
                category_id,
            )

            return 201, {"feed_id": feed["id"]}

        match = re.fullmatch(r"/v1/feeds/(\d+)", path)

        if method == "PUT" and match:
            feed_id = int(match.group(1))

            feed = next(
                (feed for feed in self._feeds if feed["id"] == feed_id),
                None,
            )

            if feed is None:
                return 404, {"error_message": "Feed not found"}

            category_id = payload.get("category_id")

            feed["category_id"] = category_id

            return 200, dict(feed)

        match = re.fullmatch(r"/v1/feeds/(\d+)/refresh", path)

        if method == "PUT" and match:
            feed_id = int(match.group(1))

            feed = next(
                (feed for feed in self._feeds if feed["id"] == feed_id),
                None,
            )

            if feed is None:
                return 404, {"error_message": "Feed not found"}

            self._emit_entries(feed_id)

            return 204, None

        if method == "GET" and path == "/v1/entries":
            entries, total = self._query_entries(query)

            return 200, {
                "total": total,
                "entries": entries,
            }

        return 404, {"error_message": "Invalid API endpoint"}

    def _register_feed(self, title, feed_url, category_id):
        feed = {
            "id": self._next_feed_id,
            "user_id": 1,
            "title": title,
            "feed_url": feed_url,
            "site_url": "",
            "category_id": category_id,
            "checked_at": None,
            "entries_count": 0,
        }
        self._next_feed_id += 1
        self._feeds.append(feed)

        return dict(feed)

    def _emit_entries(self, feed_id):
        feed = next(
            feed for feed in self._feeds if feed["id"] == feed_id
        )
        feed["checked_at"] = self._next_entry_id

        pending = self._scheduled.pop(feed_id, [])
        feed["entries_count"] += len(pending)

        feed_data = {
            "title": feed["title"],
            "site_url": feed["site_url"],
            "category": {
                "id": feed["category_id"],
                "title": self._category_title(feed["category_id"]),
            },
        }

        for source in pending:
            entry = _build_entry(
                self._next_entry_id,
                feed_id,
                feed_data,
                source,
            )
            self._next_entry_id += 1
            self._entries.append(entry)

    def _category_title(self, category_id):
        return next(
            (
                category["title"]
                for category in self._categories
                if category["id"] == category_id
            ),
            "",
        )

    def _query_entries(self, query):
        entries = list(self._entries)

        category_id = _as_int(query.get("category_id"))

        if category_id is not None:
            feed_ids = {
                feed["id"]
                for feed in self._feeds
                if feed["category_id"] == category_id
            }
            entries = [
                entry
                for entry in entries
                if entry["feed_id"] in feed_ids
            ]

        published_after = _as_int(query.get("published_after"))

        if published_after is not None:
            entries = [
                entry
                for entry in entries
                if _parse_time(entry["published_at"]) >= published_after
            ]

        published_before = _as_int(query.get("published_before"))

        if published_before is not None:
            entries = [
                entry
                for entry in entries
                if _parse_time(entry["published_at"]) <= published_before
            ]

        status = query.get("status")

        if status:
            entries = [
                entry for entry in entries if entry["status"] == status
            ]

        total = len(entries)
        entries = sorted(entries, key=lambda entry: entry["id"],
                         reverse=True)

        limit = _as_int(query.get("limit"))

        if limit is None:
            limit = total
        else:
            limit = max(0, min(limit, 100))

        offset = _as_int(query.get("offset")) or 0
        page = entries[offset:offset + limit]

        return [dict(entry) for entry in page], total