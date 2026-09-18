
from alf.router import route
from alf.routes import Route


def test_route_system_question():
    assert route("What operating system am I running?") == Route.SYSTEM


def test_route_os_question():
    assert route("What OS am I running?") == Route.SYSTEM


def test_route_general_question_to_llm():
    assert route("What does pytest -q mean?") == Route.LLM


def test_route_memory_question():
    assert route("What did we decide about SearXNG?") == Route.MEMORY


def test_route_research_question():
    assert route("What is the latest version of Python?") == Route.RESEARCH


def test_route_person_activity_question_not_news(monkeypatch):
    monkeypatch.setattr("alf.router.classify", lambda question: Route.RESEARCH)

    assert route(
        "What has Boris Johnson said recently about the economy?"
    ) == Route.RESEARCH
    assert route("What did Boris Johnson do yesterday?") == Route.RESEARCH


def test_route_non_news_question_falls_back_to_classifier(monkeypatch):
    monkeypatch.setattr("alf.router.classify", lambda question: Route.RESEARCH)

    assert route("Who is the current Prime Minister?") == Route.RESEARCH
