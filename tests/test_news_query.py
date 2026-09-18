from datetime import UTC, datetime, timedelta

import pytest

from alf import news
from alf.miniflux import Miniflux
from alf.news_intent import NewsIntent, NewsWindow
from tests.fake_miniflux import FakeMiniflux


@pytest.fixture
def fake():
    return FakeMiniflux()


def make_client(fake):
    return Miniflux(
        "http://fake:8765",
        fake.api_key,
        transport=fake.transport(),
    )


@pytest.fixture
def seeded(fake, database):
    client = make_client(fake)
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

    return client


def feed_for(client, subject):
    category = next(
        category
        for category in client.get_categories()
        if category["title"] == subject
    )

    return client.get_feeds(category_id=category["id"])[0]


def schedule(fake, client, subject, entries):
    fake.schedule_entries(feed_for(client, subject)["id"], entries)
    news.refresh(subject, client=client)


def now_timestamp():
    return int(datetime.now(UTC).timestamp())


def test_query_items_matches_by_topic(fake, seeded, database):
    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Ukraine economy shows strong growth",
                "url": "https://feeds.example/n/1",
                "published_at": now_timestamp(),
            },
            {
                "title": "Fighting continues in the east",
                "url": "https://feeds.example/n/2",
                "published_at": now_timestamp(),
            },
        ],
    )

    items = news.query_items(news.NewsQuery(topics=("economy",)))

    assert len(items) == 1
    assert items[0]["title"] == "Ukraine economy shows strong growth"
    assert items[0]["matched_terms"] == ["economy"]
    assert items[0]["content"] is None


def test_query_items_matches_any_topic(fake, seeded, database):
    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Ukraine economy shows strong growth",
                "url": "https://feeds.example/n/1",
                "published_at": now_timestamp(),
            },
            {
                "title": "Fighting continues in the east",
                "url": "https://feeds.example/n/2",
                "published_at": now_timestamp(),
            },
        ],
    )

    items = news.query_items(news.NewsQuery(topics=("economy", "fighting")))

    assert sorted(item["title"] for item in items) == [
        "Fighting continues in the east",
        "Ukraine economy shows strong growth",
    ]


def test_query_items_filters_by_inclusive_window(fake, seeded, database):
    now = datetime.now(UTC)
    recent = int((now - timedelta(hours=1)).timestamp())
    old = int((now - timedelta(days=2)).timestamp())

    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Recent story",
                "url": "https://feeds.example/n/recent",
                "published_at": recent,
            },
            {
                "title": "Old story",
                "url": "https://feeds.example/n/old",
                "published_at": old,
            },
        ],
    )

    start = now - timedelta(days=1)
    query = news.NewsQuery(
        topics=("story",),
        start=start,
        end=now,
    )

    items = news.query_items(query)

    assert [item["title"] for item in items] == ["Recent story"]

    inclusive = news.NewsQuery(
        topics=("story",),
        start=datetime.fromtimestamp(recent, tz=UTC),
        end=now,
    )

    assert [item["title"] for item in news.query_items(inclusive)] == [
        "Recent story",
    ]


def test_query_items_aligns_to_subject(fake, seeded, database):
    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Ukraine headline",
                "url": "https://feeds.example/n/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    schedule(
        fake,
        seeded,
        "Climate",
        [
            {
                "title": "Climate headline",
                "url": "https://feeds.example/c/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    items = news.query_items(news.NewsQuery(subject="Ukraine"))

    assert len(items) == 1
    assert items[0]["title"] == "Ukraine headline"


def test_query_items_aligns_subject_by_substring(fake, seeded, database):
    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Ukraine headline",
                "url": "https://feeds.example/n/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    schedule(
        fake,
        seeded,
        "Climate",
        [
            {
                "title": "Climate headline",
                "url": "https://feeds.example/c/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    items = news.query_items(news.NewsQuery(subject="ukr"))

    assert len(items) == 1
    assert items[0]["title"] == "Ukraine headline"


def test_query_items_filters_topics_within_subject(
    fake, seeded, database
):
    news.add_subject(
        "Tech",
        ["https://feeds.example/tech.rss"],
        client=seeded,
    )

    schedule(
        fake,
        seeded,
        "Tech",
        [
            {
                "title": "Quantum computing breakthrough",
                "url": "https://feeds.example/t/1",
                "published_at": now_timestamp(),
            },
            {
                "title": "New graphics card announced",
                "url": "https://feeds.example/t/2",
                "published_at": now_timestamp(),
            },
        ],
    )

    schedule(
        fake,
        seeded,
        "Climate",
        [
            {
                "title": "Quantum computing used for climate modelling",
                "url": "https://feeds.example/c/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    items = news.query_items(
        news.NewsQuery(
            subject="Tech",
            topics=("quantum",),
        )
    )

    assert len(items) == 1
    assert items[0]["title"] == "Quantum computing breakthrough"
    assert items[0]["matched_terms"] == ["quantum"]


def test_query_items_returns_newest_first(fake, seeded, database):
    base = now_timestamp()

    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Oldest",
                "url": "https://feeds.example/n/1",
                "published_at": base,
            },
            {
                "title": "Newest",
                "url": "https://feeds.example/n/2",
                "published_at": base + 100,
            },
            {
                "title": "Middle",
                "url": "https://feeds.example/n/3",
                "published_at": base + 50,
            },
        ],
    )

    items = news.query_items(news.NewsQuery(topics=("oldest", "newest", "middle")))

    assert [item["title"] for item in items] == [
        "Newest",
        "Middle",
        "Oldest",
    ]


def test_query_items_respects_limit(fake, seeded, database):
    base = now_timestamp()

    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": f"Story {index}",
                "url": f"https://feeds.example/n/{index}",
                "published_at": base + index,
            }
            for index in range(5)
        ],
    )

    items = news.query_items(
        news.NewsQuery(topics=("story", "notpresent"), limit=2)
    )

    assert len(items) == 2
    assert items[0]["title"] == "Story 4"
    assert items[1]["title"] == "Story 3"


def test_query_items_returns_empty_when_nothing_matches(fake, seeded, database):
    schedule(
        fake,
        seeded,
        "Ukraine",
        [
            {
                "title": "Ukraine headline",
                "url": "https://feeds.example/n/1",
                "published_at": now_timestamp(),
            }
        ],
    )

    assert news.query_items(news.NewsQuery(topics=("banana",))) == []


def test_query_items_requires_topic_or_subject(database):
    with pytest.raises(news.NewsError):
        news.query_items(news.NewsQuery())


def test_query_items_rejects_invalid_limit(database):
    with pytest.raises(news.NewsError):
        news.query_items(news.NewsQuery(topics=("x",), limit=0))

    with pytest.raises(news.NewsError):
        news.query_items(news.NewsQuery(topics=("x",), limit=101))


def test_news_query_from_intent():
    start = datetime(2026, 8, 20, tzinfo=UTC)
    end = datetime(2026, 8, 27, tzinfo=UTC)

    intent = NewsIntent(
        topics=("searxng",),
        window=NewsWindow(start, end, 7),
        original="What happened with SearXNG in the last 7 days?",
    )

    query = news.NewsQuery.from_intent(intent)

    assert query.topics == ("searxng",)
    assert query.start is start
    assert query.end is end
    assert query.limit == 25
    assert query.subject is None
