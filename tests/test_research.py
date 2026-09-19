import json

from alf import research


def test_search_web_returns_duckduckgo_results(monkeypatch):
    html = """
    <div class="result">
        <a class="result__a" href="https://example.com/page">
            Example page
        </a>
    </div>
    <div class="result">
        <a class="result__a" href="https://duckduckgo.com/about">
            DuckDuckGo
        </a>
    </div>
    """

    monkeypatch.setattr(
        research,
        "fetch",
        lambda url: html.encode("utf-8"),
    )

    result = research.search_web("something useful")

    assert result == [
        {
            "source": "web",
            "title": "Example page",
            "url": "https://example.com/page",
        }
    ]


def test_search_web_returns_empty_list_when_unavailable(monkeypatch):
    def unavailable(url):
        raise OSError("connection refused")

    monkeypatch.setattr(research, "fetch", unavailable)

    result = research.search_web("something unknown")

    assert result == []


def test_prepare_search_query_extracts_quoted_title():
    question = 'Who wrote "The Moon\'s a Balloon"?'

    assert research.prepare_search_query(question) == "The Moon's a Balloon"


def test_prepare_search_query_extracts_subject_of_who_wrote_question():
    question = "who wrote the moon's a balloon"

    assert research.prepare_search_query(question) == "the moon's a balloon"


def test_split_into_passages():
    text = "one two three four five"

    assert research.split_into_passages(text, max_words=2) == [
        "one two",
        "three four",
        "five",
    ]


def test_rank_passages_prefers_matching_passage():
    documents = [
        {
            "title": "Unrelated",
            "url": "https://example.com/unrelated",
            "domain": "example.com",
            "passages": ["apples and oranges"],
        },
        {
            "title": "Relevant",
            "url": "https://example.org/relevant",
            "domain": "example.org",
            "passages": ["the moon's a balloon was written by David Niven"],
        },
    ]

    ranked = research.rank_passages(
        "Who wrote The Moon's a Balloon?",
        documents,
    )

    assert ranked[0]["title"] == "Relevant"


def test_build_source_diverse_pool_keeps_authoritative_source():
    ranked = [
        {
            "title": "General source",
            "url": "https://example.com/page",
            "domain": "example.com",
            "text": "general evidence",
            "score": 10.0,
        },
        {
            "title": "Official source",
            "url": "https://gov.uk/page",
            "domain": "gov.uk",
            "text": "official evidence",
            "score": 5.0,
        },
    ]

    selected = research.build_source_diverse_pool(ranked)

    assert selected[0]["domain"] == "gov.uk"
