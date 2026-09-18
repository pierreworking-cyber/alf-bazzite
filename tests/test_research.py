import json

from alf import research


def test_search_web_returns_empty_list_when_no_results(monkeypatch):
    response = json.dumps({"results": []})

    monkeypatch.setattr(
        research,
        "fetch",
        lambda url: response,
    )

    result = research.search_web("something unknown")

    assert result == []


def test_search_web_returns_empty_list_when_searxng_unavailable(monkeypatch):
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
