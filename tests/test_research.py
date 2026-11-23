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
        <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fpage%3Fanswer%3D42%26source%3Dtest">
            Wrapped result
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
        },
        {
            "source": "web",
            "title": "Wrapped result",
            "url": "https://example.org/page?answer=42&source=test",
        },
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
def test_search_web_uses_lite_when_html_is_challenged(monkeypatch):
    challenge = "Unfortunately, bots use DuckDuckGo too."

    lite_html = """
    <a class="result-link" href="https://example.org/answer">
        Lite search result
    </a>
    """

    requested_urls = []

    def fake_fetch(request):
        requested_urls.append(request.full_url)

        if request.full_url == research.DDG_HTML_URL:
            return challenge.encode("utf-8")

        return lite_html.encode("utf-8")

    monkeypatch.setattr(research, "fetch", fake_fetch)

    result = research.search_web("something useful")

    assert requested_urls == [
        research.DDG_HTML_URL,
        research.DDG_LITE_URL,
    ]

    assert result == [
        {
            "source": "web",
            "title": "Lite search result",
            "url": "https://example.org/answer",
        }
    ]


def test_search_web_uses_lite_when_html_has_no_results(monkeypatch):
    lite_html = """
    <a class="result-link" href="https://example.org/answer">
        Lite search result
    </a>
    """

    def fake_fetch(request):
        if request.full_url == research.DDG_HTML_URL:
            return b"<html><body>No results</body></html>"

        return lite_html.encode("utf-8")

    monkeypatch.setattr(research, "fetch", fake_fetch)

    result = research.search_web("something useful")

    assert result == [
        {
            "source": "web",
            "title": "Lite search result",
            "url": "https://example.org/answer",
        }
    ]


def test_evaluate_evidence_passes_candidates_to_generate_json(monkeypatch):
    captured = {}

    def fake_generate_json(prompt):
        captured["prompt"] = prompt
        return {
            "answer": "David Niven wrote the book.",
            "confidence": "high",
            "supporting_candidates": [1],
            "rejected_candidates": [],
            "reason": "The source directly supports the answer.",
        }

    monkeypatch.setattr(
        research,
        "generate_json",
        fake_generate_json,
    )

    candidates = [
        {
            "domain": "example.org",
            "title": "Book information",
            "url": "https://example.org/book",
            "text": "David Niven wrote The Moon's a Balloon.",
        }
    ]

    result = research.evaluate_evidence(
        "Who wrote The Moon's a Balloon?",
        candidates,
    )

    assert "Who wrote The Moon's a Balloon?" in captured["prompt"]
    assert "Candidate 1" in captured["prompt"]
    assert "example.org" in captured["prompt"]
    assert "David Niven wrote The Moon's a Balloon." in captured["prompt"]
    assert "supporting_candidates" in captured["prompt"]
    assert result["answer"] == "David Niven wrote the book."


def test_evaluate_evidence_returns_generate_json_result_unchanged(monkeypatch):
    expected = {
        "answer": "The answer.",
        "confidence": "medium",
        "supporting_candidates": [1, 2],
        "rejected_candidates": [3],
        "reason": "Two sources support the answer.",
    }

    monkeypatch.setattr(
        research,
        "generate_json",
        lambda prompt: expected,
    )

    result = research.evaluate_evidence("A question?", [])

    assert result is expected


def test_select_evidence_returns_selected_candidates():
    candidates = [
        {"title": "First"},
        {"title": "Second"},
        {"title": "Third"},
    ]

    evaluation = {
        "supporting_candidates": [1, 3],
    }

    selected = research.select_evidence(
        candidates,
        evaluation,
    )

    assert selected == [
        candidates[0],
        candidates[2],
    ]


def test_select_evidence_ignores_invalid_candidate_indexes():
    candidates = [
        {"title": "First"},
        {"title": "Second"},
    ]

    evaluation = {
        "supporting_candidates": [0, 3, "1", None, 2],
    }

    selected = research.select_evidence(
        candidates,
        evaluation,
    )

    assert selected == [candidates[1]]


def test_select_evidence_returns_empty_list_when_nothing_is_supported():
    candidates = [
        {"title": "First"},
        {"title": "Second"},
    ]

    evaluation = {
        "supporting_candidates": [],
    }

    selected = research.select_evidence(
        candidates,
        evaluation,
    )

    assert selected == []
