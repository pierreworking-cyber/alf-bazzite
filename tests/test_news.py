import json
import os
import re
from datetime import UTC, datetime, timedelta

import pytest

from alf import commands, memory, news
from alf.miniflux import Miniflux, MinifluxError
from tests.fake_miniflux import FakeMiniflux

ENTRY_ONE = 1700000000
ENTRY_TWO = 1700000100


@pytest.fixture
def fake():
    return FakeMiniflux()


def make_client(fake):
    return Miniflux(
        "http://fake:8765",
        fake.api_key,
        transport=fake.transport(),
    )


def configure_news(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "CONFIG", tmp_path / "news.toml")


def config_path(tmp_path, monkeypatch):
    configure_news(tmp_path, monkeypatch)
    return news.CONFIG


def test_capability(database):
    capability = news.get_capability()

    assert capability["id"] == "news"
    assert capability["name"] == "News"
    assert capability["description"] == (
        "Subscribed news items via Miniflux"
    )
    assert capability["details"] == {
        "subjects": [],
        "feeds": 0,
        "items": 0,
    }


def test_news_api_is_reexported_by_memory():
    assert memory.add_subject is news.add_subject
    assert memory.refresh is news.refresh
    assert memory.list_items is news.list_items
    assert memory.query_items is news.query_items
    assert memory.initialise is news.initialise


def test_database_schema_creates_news_tables(database):
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
                AND name LIKE 'news_%'
                """
            ).fetchall()
        }

    assert version == 8
    assert tables == {
        "news_subjects",
        "news_feeds",
        "news_items",
    }


def test_database_upgrades_from_version_six(database):
    connection = memory.sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 6")
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
                AND name LIKE 'news_%'
                """
            ).fetchall()
        }

    assert version == 8
    assert tables == {
        "news_subjects",
        "news_feeds",
        "news_items",
    }


def test_initialise_writes_private_config(fake, database, tmp_path, monkeypatch):
    config = config_path(tmp_path, monkeypatch)

    assert news.initialise(
        "http://fake:8765",
        "secret",
        client=make_client(fake),
    ) is True

    assert config.read_text() == (
        'base_url = "http://fake:8765"\n'
        'api_key = "secret"\n'
    )
    assert os.stat(config).st_mode & 0o777 == 0o600

    assert news.get_news_config() == {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    }


def test_initialise_rejects_unreachable_service(database, tmp_path, monkeypatch):
    config = config_path(tmp_path, monkeypatch)

    rejecting = FakeMiniflux(api_key="server-key")
    failing_client = Miniflux(
        "http://fake:8765",
        "wrong-key",
        transport=rejecting.transport(),
    )

    with pytest.raises(MinifluxError):
        news.initialise(
            "http://fake:8765",
            "wrong-key",
            client=failing_client,
        )

    assert not config.exists()


def test_get_client_requires_configuration(database, tmp_path, monkeypatch):
    config = config_path(tmp_path, monkeypatch)

    with pytest.raises(news.NewsError):
        news.get_client()

    assert not config.exists()


def test_add_subject_creates_subject_category_and_feeds(fake, database):
    client = make_client(fake)

    first = "https://feeds.example/ukraine.rss"
    second = "https://feeds.example/nature.rss"

    result = news.add_subject(
        "Ukraine",
        [first, second],
        client=client,
    )

    assert result == {
        "subject": "Ukraine",
        "added": [first, second],
        "existing": [],
    }

    assert news.get_news_information() == {
        "subjects": [
            {"id": 1, "name": "Ukraine"},
        ],
        "feeds": 2,
        "items": 0,
    }

    categories = client.get_categories()
    assert [category["title"] for category in categories] == [
        "Ukraine",
    ]

    feeds = client.get_feeds(category_id=categories[0]["id"])
    assert [feed["feed_url"] for feed in feeds] == [first, second]


def test_add_subject_adds_more_feeds_to_existing_subject(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    result = news.add_subject(
        "Ukraine",
        ["https://feeds.example/nature.rss"],
        client=client,
    )

    assert result == {
        "subject": "Ukraine",
        "added": ["https://feeds.example/nature.rss"],
        "existing": [],
    }

    assert news.get_news_information()["feeds"] == 2
    assert len(client.get_categories()) == 1


def test_add_subject_reports_existing_feeds(fake, database):
    client = make_client(fake)

    first = "https://feeds.example/ukraine.rss"

    news.add_subject("Ukraine", [first], client=client)

    result = news.add_subject("Ukraine", [first], client=client)

    assert result == {
        "subject": "Ukraine",
        "added": [],
        "existing": [first],
    }

    assert news.get_news_information()["feeds"] == 1
    assert news.get_news_information()["subjects"] == [
        {"id": 1, "name": "Ukraine"},
    ]


def test_list_subjects_returns_subjects_with_feed_and_item_counts(
    fake,
    database,
):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        [
            "https://feeds.example/ukraine.rss",
            "https://feeds.example/world.rss",
        ],
        client=client,
    )
    news.add_subject(
        "Climate",
        ["https://feeds.example/climate.rss"],
        client=client,
    )

    ukraine_feeds = client.get_feeds(category_id=1)

    fake.schedule_entries(
        ukraine_feeds[0]["id"],
        [
            {
                "title": "Ukraine story",
                "url": "https://feeds.example/ukraine/1",
                "published_at": ENTRY_ONE,
            },
            {
                "title": "Another Ukraine story",
                "url": "https://feeds.example/ukraine/2",
                "published_at": ENTRY_TWO,
            },
        ],
    )

    news.refresh("Ukraine", client=client)

    assert news.list_subjects() == [
        {
            "id": 2,
            "name": "Climate",
            "feeds": 1,
            "items": 0,
        },
        {
            "id": 1,
            "name": "Ukraine",
            "feeds": 2,
            "items": 2,
        },
    ]


def test_add_subject_requires_name_and_feed_urls(database):
    with pytest.raises(news.NewsError):
        news.add_subject("  ", ["https://feeds.example/x.rss"])

    with pytest.raises(news.NewsError):
        news.add_subject("Ukraine", ["   "])

    with pytest.raises(news.NewsError):
        news.add_subject("Ukraine", [])


def test_refresh_imports_entries(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    feed = client.get_feeds(category_id=1)[0]

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
                "summary": "Summary of the first story.",
            },
            {
                "title": "News Two",
                "url": "https://feeds.example/news/2",
                "published_at": ENTRY_TWO,
            },
        ],
    )

    result = news.refresh("Ukraine", client=client)

    assert result == {
        "subject": "Ukraine",
        "refreshed": 1,
        "imported": 2,
        "skipped": 0,
        "failures": [],
        "subjects": [
            {
                "name": "Ukraine",
                "new_items": 2,
            }
        ],
    }

    items = news.list_items("Ukraine")

    assert [item["title"] for item in items] == [
        "News Two",
        "News One",
    ]
    assert items[0]["summary"] == ""
    assert items[1]["summary"] == "Summary of the first story."
    assert items[0]["feed_title"] == (
        "https://feeds.example/ukraine.rss"
    )

    assert news.get_news_information()["items"] == 2


def test_refresh_imports_entries_from_each_feed(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        [
            "https://feeds.example/busy.rss",
            "https://feeds.example/quiet.rss",
        ],
        client=client,
    )

    feeds = client.get_feeds(category_id=1)

    busy_feed = next(
        feed for feed in feeds
        if feed["feed_url"] == "https://feeds.example/busy.rss"
    )
    quiet_feed = next(
        feed for feed in feeds
        if feed["feed_url"] == "https://feeds.example/quiet.rss"
    )

    fake.schedule_entries(
        busy_feed["id"],
        [
            {
                "title": f"Busy News {index}",
                "url": f"https://feeds.example/busy/{index}",
                "published_at": ENTRY_ONE + index,
            }
            for index in range(100)
        ],
    )

    fake.schedule_entries(
        quiet_feed["id"],
        [
            {
                "title": "Quiet News",
                "url": "https://feeds.example/quiet/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.refresh("Ukraine", client=client)

    assert result["refreshed"] == 2
    assert result["imported"] == 101

    items = news.list_items("Ukraine")

    assert len(items) == 101
    assert any(item["title"] == "Quiet News" for item in items)


def test_refresh_registers_new_miniflux_feed(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    category = client.get_categories()[0]
    new_feed = fake.add_feed(
        "Ukraine News",
        "https://feeds.example/new.rss",
        category_id=category["id"],
    )

    fake.schedule_entries(
        new_feed["id"],
        [
            {
                "title": "New Feed Story",
                "url": "https://feeds.example/news/new",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.refresh("Ukraine", client=client)

    assert result["refreshed"] == 2
    assert result["imported"] == 1

    feeds = news.get_news_feeds()
    assert len(feeds) == 2
    assert any(feed["title"] == "Ukraine News" for feed in feeds)

    items = news.list_items("Ukraine")
    assert len(items) == 1
    assert items[0]["title"] == "New Feed Story"


def test_refresh_without_arguments_refreshes_everything(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    feed = client.get_feeds(category_id=1)[0]

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.refresh(client=client)

    assert result["subject"] is None
    assert result["imported"] == 1
    assert len(news.list_items()) == 1


def test_refresh_is_idempotent(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    feed = client.get_feeds(category_id=1)[0]

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    first = news.refresh("Ukraine", client=client)

    assert first["imported"] == 1

    second = news.refresh("Ukraine", client=client)

    assert second["imported"] == 0
    assert second["skipped"] == 1

    assert len(news.list_items("Ukraine")) == 1


def test_refresh_imports_only_new_entries(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    feed = client.get_feeds(category_id=1)[0]

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    news.refresh("Ukraine", client=client)

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News Two",
                "url": "https://feeds.example/news/2",
                "published_at": ENTRY_TWO,
            }
        ],
    )

    result = news.refresh("Ukraine", client=client)

    assert result["imported"] == 1
    assert result["skipped"] == 1

    assert len(news.list_items("Ukraine")) == 2


def test_refresh_survives_miniflux_purge_and_id_reuse(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    feed = client.get_feeds(category_id=1)[0]

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    news.refresh("Ukraine", client=client)

    fake.purge_entries()

    fake.schedule_entries(
        feed["id"],
        [
            {
                "title": "News One Again",
                "url": "https://feeds.example/news/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.refresh("Ukraine", client=client)

    assert result["imported"] == 0
    assert result["skipped"] == 1

    items = news.list_items("Ukraine")

    assert len(items) == 1
    assert items[0]["title"] == "News One"


def test_refresh_reports_feed_failures_without_aborting(fake, database):
    client = make_client(fake)

    news.add_subject(
        "Ukraine",
        [
            "https://feeds.example/failing.rss",
            "https://feeds.example/working.rss",
        ],
        client=client,
    )

    feeds = client.get_feeds(category_id=1)

    failing_feed = next(
        feed for feed in feeds
        if feed["feed_url"] == "https://feeds.example/failing.rss"
    )
    working_feed = next(
        feed for feed in feeds
        if feed["feed_url"] == "https://feeds.example/working.rss"
    )

    fake.schedule_entries(
        working_feed["id"],
        [
            {
                "title": "Working Feed Story",
                "url": "https://feeds.example/working/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    def failing_transport(method, url, headers, payload, timeout):
        if (
            method == "PUT"
            and url.endswith(f"/feeds/{failing_feed['id']}/refresh")
        ):
            return 404, json.dumps(
                {"error_message": "Feed not found"}
            ).encode("utf-8")

        return fake.transport()(
            method,
            url,
            headers,
            payload,
            timeout,
        )

    failing_client = Miniflux(
        "http://fake:8765",
        fake.api_key,
        transport=failing_transport,
    )

    result = news.refresh("Ukraine", client=failing_client)

    assert result["refreshed"] == 1
    assert result["imported"] == 1
    assert len(result["failures"]) == 1
    assert result["failures"][0]["feed"] == (
        "https://feeds.example/failing.rss"
    )
    assert "not found" in result["failures"][0]["reason"].lower()

    items = news.list_items("Ukraine")

    assert len(items) == 1
    assert items[0]["title"] == "Working Feed Story"


def test_refresh_requires_stored_feeds(database, tmp_path, monkeypatch):
    config_path(tmp_path, monkeypatch)

    with pytest.raises(news.NewsError):
        news.refresh()

    with pytest.raises(news.NewsError):
        news.refresh("Ukraine")


def test_list_items_filters_by_subject_and_days(fake, database):
    client = make_client(fake)

    now = datetime.now(UTC)
    recent = int(now.timestamp())
    old = int((now - timedelta(days=3)).timestamp())

    news.add_subject(
        "Ukraine",
        ["https://feeds.example/ukraine.rss"],
        client=client,
    )

    news.add_subject(
        "Climate",
        ["https://feeds.example/climate.rss"],
        client=client,
    )

    all_feeds = []
    all_feeds.append(client.get_feeds(category_id=1)[0])
    all_feeds.append(client.get_feeds(category_id=2)[0])

    fake.schedule_entries(
        all_feeds[0]["id"],
        [
            {
                "title": "Ukraine Recent",
                "url": "https://feeds.example/u/recent",
                "published_at": recent,
            },
            {
                "title": "Ukraine Old",
                "url": "https://feeds.example/u/old",
                "published_at": old,
            },
        ],
    )

    fake.schedule_entries(
        all_feeds[1]["id"],
        [
            {
                "title": "Climate Recent",
                "url": "https://feeds.example/c/recent",
                "published_at": recent + 5,
            }
        ],
    )

    news.refresh(client=client)

    assert [item["subject"] for item in news.list_items()] == [
        "Climate",
        "Ukraine",
        "Ukraine",
    ]

    assert [item["title"] for item in news.list_items("Ukraine")] == [
        "Ukraine Recent",
        "Ukraine Old",
    ]

    assert [item["title"] for item in news.list_items("Climate")] == [
        "Climate Recent",
    ]

    assert [item["title"] for item in news.list_items(days=2)] == [
        "Climate Recent",
        "Ukraine Recent",
    ]

    assert [item["title"] for item in news.list_items(
        "Ukraine",
        days=2,
    )] == [
        "Ukraine Recent",
    ]


def test_list_items_returns_empty_when_nothing_stored(database):
    assert news.list_items() == []
    assert news.list_items("Ukraine") == []


def test_get_news_status_reports_unconfigured(database, tmp_path, monkeypatch):
    config_path(tmp_path, monkeypatch)

    status = news.get_news_status()

    assert status["service"] == {
        "configured": False,
        "reachable": None,
    }
    assert status["subjects"] == []
    assert status["feeds"] == 0
    assert status["items"] == 0


def test_get_news_status_reports_reachable_service(
    fake,
    database,
    tmp_path,
    monkeypatch,
):
    config_path(tmp_path, monkeypatch)

    news.initialise(
        "http://fake:8765",
        fake.api_key,
        client=make_client(fake),
    )

    status = news.get_news_status(client=make_client(fake))

    assert status["service"] == {
        "configured": True,
        "reachable": True,
    }


def test_get_news_status_reports_unreachable_service(
    fake,
    database,
    tmp_path,
    monkeypatch,
):
    config_path(tmp_path, monkeypatch)

    news.initialise(
        "http://fake:8765",
        fake.api_key,
        client=make_client(fake),
    )

    rejecting = FakeMiniflux(api_key="server-key")

    failing_client = Miniflux(
        "http://fake:8765",
        "wrong-key",
        transport=rejecting.transport(),
    )

    status = news.get_news_status(client=failing_client)

    assert status["service"] == {
        "configured": True,
        "reachable": False,
    }


def test_news_command_requires_subcommand(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "render_command_help",
        lambda command, catalogue: captured.update(
            {"command": command, "catalogue": catalogue}
        ),
    )

    commands.news_command()

    assert captured["command"] == "news"
    assert captured["catalogue"]["id"] == "news.manage"


def test_news_command_rejects_unknown_subcommand(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    commands.news_command("frobnicate")

    assert captured == ["news"]


def test_news_add_command_adds_subject(monkeypatch):
    captured = {}

    def fake_add_subject(subject, feed_urls):
        captured["subject"] = subject
        captured["feed_urls"] = feed_urls
        return {
            "subject": subject,
            "added": feed_urls,
            "existing": [],
        }

    monkeypatch.setattr(commands, "add_subject", fake_add_subject)

    monkeypatch.setattr(
        commands,
        "render_news_subject_added",
        lambda result: captured.update({"rendered": result}),
    )

    commands.news_command(
        "add",
        "Ukraine",
        "https://feeds.example/ukraine.rss",
    )

    assert captured["subject"] == "Ukraine"
    assert captured["feed_urls"] == (
        "https://feeds.example/ukraine.rss",
    )
    assert captured["rendered"] == {
        "subject": "Ukraine",
        "added": (
            "https://feeds.example/ukraine.rss",
        ),
        "existing": [],
    }


def test_news_add_command_requires_subject_and_feed(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "add_subject",
        lambda *arguments: pytest.fail(
            "add_subject should not be called"
        ),
    )

    commands.news_command("add", "Ukraine")
    commands.news_command("add")

    assert captured == ["news", "news"]


def test_news_refresh_command_refreshes_subject(monkeypatch):
    captured = {}

    def fake_refresh(subject=None):
        captured["subject"] = subject
        return {
            "subject": subject,
            "refreshed": 1,
            "imported": 0,
            "skipped": 0,
            "failures": [],
        }

    monkeypatch.setattr(commands, "refresh", fake_refresh)

    monkeypatch.setattr(
        commands,
        "render_news_refreshed",
        lambda result: captured.update({"rendered": result}),
    )

    commands.news_command("refresh", "Ukraine")

    assert captured["subject"] == "Ukraine"
    assert captured["rendered"] == {
        "subject": "Ukraine",
        "refreshed": 1,
        "imported": 0,
        "skipped": 0,
        "failures": [],
    }


def test_news_list_command_refreshes_and_lists_subjects(monkeypatch):
    captured = {}

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    refresh_result = {
        "subjects": [
            {"name": "Ukraine", "new_items": 2},
        ],
    }

    monkeypatch.setattr(
        commands,
        "refresh",
        lambda: refresh_result,
    )

    subjects = [
        {
            "id": 1,
            "name": "Ukraine",
            "feeds": 2,
            "items": 12,
        },
    ]

    monkeypatch.setattr(
        commands,
        "list_subjects",
        lambda: subjects,
    )

    monkeypatch.setattr(
        commands,
        "render_news_subjects",
        lambda subjects, result: captured.update(
            {
                "subjects": subjects,
                "result": result,
            }
        ),
    )

    commands.news_command("list")

    assert captured == {
        "subjects": subjects,
        "result": refresh_result,
    }


def test_news_list_command_hints_when_unconfigured(monkeypatch):
    captured = []

    monkeypatch.setattr(commands, "get_news_config", lambda: None)

    monkeypatch.setattr(
        commands,
        "render_news_error",
        lambda message: captured.append(message),
    )

    monkeypatch.setattr(
        commands,
        "refresh",
        lambda: pytest.fail(
            "refresh should not be called when unconfigured"
        ),
    )

    commands.news_command("list")

    assert captured == [
        "News is not configured. Run `alf news init`."
    ]


def test_news_list_command_rejects_arguments(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "refresh",
        lambda: pytest.fail(
            "refresh should not be called with arguments"
        ),
    )

    commands.news_command("list", "Ukraine")
    commands.news_command("list", "--days", "7")

    assert captured == ["news", "news"]


def test_news_status_command_requires_no_arguments(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "get_news_status",
        lambda: pytest.fail(
            "get_news_status should not be called"
        ),
    )

    commands.news_command("status", "extra")

    assert captured == ["news"]


def test_run_resolves_news_command(monkeypatch):
    captured = {}

    def fake_news_command(*arguments):
        captured["arguments"] = arguments

    monkeypatch.setitem(
        commands.command_handlers,
        "news",
        fake_news_command,
    )

    assert commands.run("news", ["refresh"]) is True

    assert captured["arguments"] == ("refresh",)


def test_news_query_command_queries_items(monkeypatch):
    captured = {}

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    def fake_query_items(query):
        captured["query"] = query
        return []

    monkeypatch.setattr(commands, "query_items", fake_query_items)

    monkeypatch.setattr(
        commands,
        "render_news_query",
        lambda items, query: captured.update(
            {"rendered": (items, query)}
        ),
    )

    commands.news_command(
        "query",
        "Ukraine",
        "--days",
        "7",
        "--limit",
        "5",
    )

    query = captured["query"]

    assert query.topics == ("ukraine",)
    assert query.limit == 5
    assert query.subject is None
    assert query.start is not None
    assert query.end is not None
    assert (query.end - query.start).days == 7
    assert captured["rendered"] == ([], query)


def test_news_query_command_queries_subject_topics(monkeypatch):
    captured = {}

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    def fake_query_items(query):
        captured["query"] = query
        return []

    monkeypatch.setattr(commands, "query_items", fake_query_items)

    monkeypatch.setattr(
        commands,
        "render_news_query",
        lambda items, query: None,
    )

    commands.news_command(
        "query",
        "Tech",
        "quantum computing",
        "--days",
        "7",
        "--limit",
        "10",
    )

    query = captured["query"]

    assert query.subject == "Tech"
    assert query.topics == ("quantum", "computing")
    assert query.limit == 10
    assert query.start is not None
    assert query.end is not None
    assert (query.end - query.start).days == 7


def test_news_query_command_refreshes_before_query(monkeypatch):
    events = []

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    def fake_refresh():
        events.append("refresh")
        return {}

    def fake_query_items(query):
        events.append("query")
        return []

    monkeypatch.setattr(commands, "refresh", fake_refresh)
    monkeypatch.setattr(commands, "query_items", fake_query_items)
    monkeypatch.setattr(
        commands,
        "render_news_query",
        lambda items, query: events.append("render"),
    )

    commands.news_command("query", "quantum computing")

    assert events == ["refresh", "query", "render"]


def test_news_query_command_defaults_to_seven_days(monkeypatch):
    captured = {}

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    def fake_query_items(query):
        captured["query"] = query
        return []

    monkeypatch.setattr(commands, "query_items", fake_query_items)

    monkeypatch.setattr(
        commands,
        "render_news_query",
        lambda items, query: None,
    )

    commands.news_command("query", "Ukraine")

    assert (captured["query"].end - captured["query"].start).days == 7


def test_news_query_command_requires_topic(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "get_news_config",
        lambda: pytest.fail("news config should not be consulted"),
    )

    commands.news_command("query")
    commands.news_command("query", "what", "the")

    assert captured == ["news", "news"]


def test_news_query_command_rejects_unknown_option(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "query_items",
        lambda *arguments, **kwargs: pytest.fail(
            "query_items should not be called"
        ),
    )

    commands.news_command("query", "Ukraine", "--bogus")

    assert captured == ["news"]


def test_news_query_command_rejects_invalid_days_and_limit(monkeypatch):
    captured = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: captured.append(command),
    )

    monkeypatch.setattr(
        commands,
        "query_items",
        lambda *arguments, **kwargs: pytest.fail(
            "query_items should not be called"
        ),
    )

    commands.news_command("query", "Ukraine", "--days", "abc")
    commands.news_command("query", "Ukraine", "--days", "0")
    commands.news_command("query", "Ukraine", "--days", "400")
    commands.news_command("query", "Ukraine", "--limit", "0")
    commands.news_command("query", "Ukraine", "--limit", "101")
    commands.news_command("query", "Ukraine", "--limit", "abc")

    assert captured == ["news"] * 6


def test_news_query_command_hints_when_unconfigured(monkeypatch):
    captured = []

    monkeypatch.setattr(commands, "get_news_config", lambda: None)

    monkeypatch.setattr(
        commands,
        "render_news_error",
        lambda message: captured.append(message),
    )

    monkeypatch.setattr(
        commands,
        "query_items",
        lambda *arguments, **kwargs: pytest.fail(
            "query_items should not be called when unconfigured"
        ),
    )

    commands.news_command("query", "Ukraine")

    assert captured == [
        "News is not configured. Run `alf news init`."
    ]


def test_news_query_command_reports_query_failure(monkeypatch):
    captured = []

    monkeypatch.setattr(commands, "get_news_config", lambda: {
        "base_url": "http://fake:8765",
        "api_key": "secret",
    })

    def failing_query_items(query):
        raise news.NewsError(
            "A news query limit must be between 1 and 100."
        )

    monkeypatch.setattr(commands, "query_items", failing_query_items)

    monkeypatch.setattr(
        commands,
        "render_news_error",
        lambda message: captured.append(message),
    )

    commands.news_command("query", "Ukraine")

    assert captured == [
        "A news query limit must be between 1 and 100."
    ]


def _move_source_feed(fake, client, name, first, second):
    """Seed two subjects and return the ALF feed id and Miniflux feed for a move."""
    news.add_subject(name, [first], client=client)
    news.add_subject("Climate", [second], client=client)

    source_category = next(
        category for category in client.get_categories()
        if category["title"] == name
    )
    source_feed = client.get_feeds(category_id=source_category["id"])[0]

    with memory.get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM news_feeds WHERE miniflux_feed_id = ?",
            (source_feed["id"],),
        ).fetchone()

    return row[0], source_feed


def _feed_subject(feed_id):
    return next(
        feed["subject"]
        for feed in news.get_news_feeds()
        if feed["id"] == feed_id
    )


def test_move_feed_changes_subject_and_miniflux_category(fake, database):
    client = make_client(fake)

    first = "https://feeds.example/ukraine.rss"
    second = "https://feeds.example/climate.rss"

    alf_feed_id, source_feed = _move_source_feed(
        fake,
        client,
        "Ukraine",
        first,
        second,
    )

    destination = next(
        category for category in client.get_categories()
        if category["title"] == "Climate"
    )
    source_category = next(
        category for category in client.get_categories()
        if category["title"] == "Ukraine"
    )

    result = news.move_feed(alf_feed_id, 2, client=client)

    assert result["subject_id"] == 2
    assert result["subject"] == "Climate"
    assert _feed_subject(alf_feed_id) == "Climate"

    feeds_in_destination = client.get_feeds(category_id=destination["id"])
    feeds_in_source = client.get_feeds(category_id=source_category["id"])

    assert source_feed["id"] in {
        feed["id"] for feed in feeds_in_destination
    }
    assert source_feed["id"] not in {
        feed["id"] for feed in feeds_in_source
    }


def test_moved_feed_is_imported_by_destination_refresh(fake, database):
    client = make_client(fake)

    alf_feed_id, source_feed = _move_source_feed(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        "https://feeds.example/climate.rss",
    )

    news.move_feed(alf_feed_id, 2, client=client)

    fake.schedule_entries(
        source_feed["id"],
        [
            {
                "title": "Moved story",
                "url": "https://feeds.example/moved/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.refresh("Climate", client=client)

    assert result["imported"] == 1
    assert [item["title"] for item in news.list_items("Climate")] == [
        "Moved story"
    ]
    assert news.list_items("Ukraine") == []


def test_move_feed_rolls_back_on_miniflux_failure(fake, database):
    client = make_client(fake)

    alf_feed_id, source_feed = _move_source_feed(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        "https://feeds.example/climate.rss",
    )

    def failing_transport(method, url, headers, payload, timeout):
        if method == "PUT" and re.search(r"/v1/feeds/\d+$", url):
            return 500, json.dumps(
                {"error_message": "Move failed"}
            ).encode("utf-8")

        return fake.transport()(
            method,
            url,
            headers,
            payload,
            timeout,
        )

    failing_client = Miniflux(
        "http://fake:8765",
        fake.api_key,
        transport=failing_transport,
    )

    with pytest.raises(MinifluxError):
        news.move_feed(alf_feed_id, 2, client=failing_client)

    assert _feed_subject(alf_feed_id) == "Ukraine"

    source_category = next(
        category for category in client.get_categories()
        if category["title"] == "Ukraine"
    )
    feeds_in_source = client.get_feeds(category_id=source_category["id"])

    assert source_feed["id"] in {
        feed["id"] for feed in feeds_in_source
    }


def test_move_feed_to_same_subject_is_noop(fake, database):
    client = make_client(fake)

    alf_feed_id, _ = _move_source_feed(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        "https://feeds.example/climate.rss",
    )

    result = news.move_feed(alf_feed_id, 1, client=client)

    assert result["subject_id"] == 1
    assert result["subject"] == "Ukraine"

    assert not any(
        request["method"] == "PUT"
        and re.search(r"/v1/feeds/\d+$", request["path"])
        for request in fake.requests
    )


def test_move_feed_recreates_missing_destination_category(fake, database):
    client = make_client(fake)

    alf_feed_id, source_feed = _move_source_feed(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        "https://feeds.example/climate.rss",
    )

    climate = next(
        category for category in client.get_categories()
        if category["title"] == "Climate"
    )
    fake._categories = [
        category
        for category in fake._categories
        if category["id"] != climate["id"]
    ]

    result = news.move_feed(alf_feed_id, 2, client=client)

    assert result["subject"] == "Climate"
    assert _feed_subject(alf_feed_id) == "Climate"

    recreated = next(
        category for category in client.get_categories()
        if category["title"] == "Climate"
    )
    assert recreated["id"] != climate["id"]
    assert source_feed["id"] in {
        feed["id"]
        for feed in client.get_feeds(category_id=recreated["id"])
    }


def _seed_subject(fake, client, name, feed_url, items=None):
    """Seed a subject and return its Miniflux category and feed."""
    news.add_subject(name, [feed_url], client=client)

    category = next(
        category
        for category in client.get_categories()
        if category["title"] == name
    )
    feed = client.get_feeds(category_id=category["id"])[0]

    if items is not None:
        fake.schedule_entries(feed["id"], items)
        news.refresh(name, client=client)

    return category, feed


def _subject_names():
    return [subject["name"] for subject in news.get_news_information()[
        "subjects"
    ]]


def test_delete_subject_removes_category_and_its_feeds(fake, database):
    client = make_client(fake)

    ukraine_category, _ = _seed_subject(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        items=[
            {
                "title": "Ukraine story",
                "url": "https://feeds.example/ukraine/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    result = news.delete_subject(1, client=client)

    assert result == {"id": 1, "name": "Ukraine"}

    assert _subject_names() == []

    assert ukraine_category["id"] not in {
        category["id"] for category in client.get_categories()
    }
    assert client.get_feeds() == []
    assert client.get_entries() == []

    assert news.get_news_information()["feeds"] == 0
    assert news.get_news_information()["items"] == 0


def test_delete_subject_preserves_other_subject_and_its_feeds(
    fake,
    database,
):
    client = make_client(fake)

    ukraine_category, _ = _seed_subject(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        items=[
            {
                "title": "Ukraine story",
                "url": "https://feeds.example/ukraine/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    climate_category, climate_feed = _seed_subject(
        fake,
        client,
        "Climate",
        "https://feeds.example/climate.rss",
    )
    climate_category_id = climate_category["id"]

    news.delete_subject(1, client=client)

    assert _subject_names() == ["Climate"]

    surviving = next(
        category
        for category in client.get_categories()
        if category["title"] == "Climate"
    )
    assert surviving["id"] == climate_category_id

    assert climate_feed["id"] in {
        feed["id"]
        for feed in client.get_feeds(category_id=surviving["id"])
    }
    assert ukraine_category["id"] not in {
        category["id"] for category in client.get_categories()
    }

    assert news.get_news_information()["feeds"] == 1
    assert news.get_news_information()["items"] == 0


def test_delete_subject_rolls_back_on_miniflux_failure(fake, database):
    client = make_client(fake)

    ukraine_category, ukraine_feed = _seed_subject(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        items=[
            {
                "title": "Ukraine story",
                "url": "https://feeds.example/ukraine/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    def failing_transport(method, url, headers, payload, timeout):
        if method == "DELETE" and re.search(r"/v1/categories/\d+$", url):
            return 500, json.dumps(
                {"error_message": "Delete failed"}
            ).encode("utf-8")

        return fake.transport()(
            method,
            url,
            headers,
            payload,
            timeout,
        )

    failing_client = Miniflux(
        "http://fake:8765",
        fake.api_key,
        transport=failing_transport,
    )

    with pytest.raises(MinifluxError):
        news.delete_subject(1, client=failing_client)

    assert _subject_names() == ["Ukraine"]
    assert ukraine_category["id"] in {
        category["id"] for category in client.get_categories()
    }
    assert ukraine_feed["id"] in {
        feed["id"]
        for feed in client.get_feeds(category_id=ukraine_category["id"])
    }
    assert news.get_news_information()["feeds"] == 1
    assert news.get_news_information()["items"] == 1


def test_delete_subject_missing_makes_no_miniflux_changes(fake, database):
    client = make_client(fake)

    with pytest.raises(news.NewsError):
        news.delete_subject(999, client=client)

    assert fake.requests == []
    assert _subject_names() == []


def test_delete_subject_missing_miniflux_category_rolls_back(
    fake,
    database,
):
    client = make_client(fake)

    ukraine_category, _ = _seed_subject(
        fake,
        client,
        "Ukraine",
        "https://feeds.example/ukraine.rss",
        items=[
            {
                "title": "Ukraine story",
                "url": "https://feeds.example/ukraine/1",
                "published_at": ENTRY_ONE,
            }
        ],
    )

    fake._categories = [
        category
        for category in fake._categories
        if category["id"] != ukraine_category["id"]
    ]

    with pytest.raises(news.NewsError) as excinfo:
        news.delete_subject(1, client=client)

    assert "could not be found" in str(excinfo.value)

    assert _subject_names() == ["Ukraine"]
    assert news.get_news_information()["feeds"] == 1
    assert news.get_news_information()["items"] == 1
