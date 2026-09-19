import pytest

from alf import commands, question
from alf.news_intent import NewsIntent, NewsWindow
from alf.routes import Route


def test_question_command_passes_question_to_question_engine(monkeypatch):
    captured = {}

    result = question.QuestionResult(
        answer="Python's len() function returns the number of items.",
        source="llm",
        research_question="What does Python's len() function return?",
    )

    def fake_answer_question(original_question, verbose=False):
        captured["original_question"] = original_question
        captured["verbose"] = verbose
        return result

    monkeypatch.setattr(
        commands,
        "answer_question",
        fake_answer_question,
    )

    output = []

    monkeypatch.setattr(
        commands,
        "render_question",
        lambda answer, source, research_question, news_items=None: output.append(
            (answer, source, research_question, news_items)
        ),
    )

    commands.question_command(
        "What",
        "does",
        "Python's",
        "len()",
        "function",
        "return?",
    )

    assert captured == {
        "original_question": "What does Python's len() function return?",
        "verbose": False,
    }

    assert output == [
        (
            "Python's len() function returns the number of items.",
            "llm",
            "What does Python's len() function return?",
            None,
        )
    ]


def test_question_command_passes_news_items_to_question_engine(monkeypatch):
    captured = {}

    news_items = [
        {
            "id": 1,
            "subject": "Ukraine",
            "feed_title": "https://feeds.example/ukraine.rss",
            "title": "Ukraine economy shows strong growth",
            "url": "https://feeds.example/n/1",
            "summary": "",
            "published_at": "2026-08-27T10:00:00Z",
            "first_seen_at": "2026-08-27T10:01:00",
            "matched_terms": ["economy"],
            "content": None,
        }
    ]

    result = question.QuestionResult(
        answer="Ukraine's economy grew strongly last week [1].",
        source="news",
        research_question=None,
        news_items=news_items,
    )

    def fake_answer_question(original_question, verbose=False):
        captured["original_question"] = original_question
        return result

    monkeypatch.setattr(
        commands,
        "answer_question",
        fake_answer_question,
    )

    output = []

    monkeypatch.setattr(
        commands,
        "render_question",
        lambda answer, source, research_question, news_items=None: output.append(
            (answer, source, research_question, news_items)
        ),
    )

    commands.question_command(
        "What",
        "has",
        "happened",
        "in",
        "Ukraine",
        "recently?",
    )

    assert captured["original_question"] == (
        "What has happened in Ukraine recently?"
    )

    assert output == [
        (
            "Ukraine's economy grew strongly last week [1].",
            "news",
            None,
            news_items,
        )
    ]


def test_answer_question_admits_when_no_research_is_relevant(monkeypatch):
    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.RESEARCH,
    )

    monkeypatch.setattr(
        question,
        "interpret_question",
        lambda question: question,
    )

    monkeypatch.setattr(
        question,
        "research_web",
        lambda question: [],
    )

    monkeypatch.setattr(
        question,
        "evaluate_research",
        lambda question, candidates: {
            "relevant": False,
            "candidates": [],
            "reason": "No reliable evidence.",
        },
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *arguments, **kwargs: pytest.fail(
            "ALF must not answer without evidence"
        ),
    )

    result = question.answer_question(
        "What film is this?"
    )

    assert result.answer == (
        "I couldn't find reliable research that answers your question. "
        "I don't want to guess."
    )
    assert result.source is None
    assert result.research_question == "What film is this?"



def test_answer_question_passes_all_relevant_research_candidates(
    monkeypatch,
):
    candidates = [
        {
            "title": "First source",
            "url": "https://example.com/first",
            "text": "Evidence from the first source.",
        },
        {
            "title": "Second source",
            "url": "https://example.com/second",
            "text": "Evidence from the second source.",
        },
    ]

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.RESEARCH,
    )

    monkeypatch.setattr(
        question,
        "interpret_question",
        lambda question: question,
    )

    monkeypatch.setattr(
        question,
        "research_web",
        lambda question: candidates,
    )

    monkeypatch.setattr(
        question,
        "evaluate_research",
        lambda question, candidates: {
            "relevant": True,
            "candidates": [1, 2],
            "reason": "Both sources support the answer.",
        },
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
    ):
        captured["evidence"] = evidence
        return "Answer from both sources."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question(
        "What happened?"
    )

    assert captured["evidence"] == candidates
    assert result.answer == "Answer from both sources."
    assert result.source == "web"
    assert result.research_question == "What happened?"

def test_answer_question_uses_system_information(monkeypatch):
    system_information = {
        "operating_system": "Linux",
        "hostname": "alf-machine",
        "architecture": "x86_64",
        "python_version": "3.14.6",
    }

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.SYSTEM,
    )

    monkeypatch.setattr(
        question,
        "get_system_information",
        lambda: system_information,
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
    ):
        captured["answer_request"] = {
            "original_question": original_question,
            "research_question": research_question,
            "evidence": evidence,
            "verbose": verbose,
        }
        return "You are running Linux."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question(
        "What operating system am I running?"
    )

    assert captured["answer_request"] == {
        "original_question": "What operating system am I running?",
        "research_question": "What operating system am I running?",
        "evidence": [system_information],
        "verbose": False,
    }

    assert result.answer == "You are running Linux."
    assert result.source == "system"
    assert result.research_question is None


def test_answer_question_uses_memory_when_relevant(monkeypatch):
    memories = [
        {
            "id": 1,
            "category": "decision",
            "status": "active",
            "content": "ALF should use evidence rather than guesses.",
        }
    ]

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.MEMORY,
    )

    monkeypatch.setattr(
        question,
        "find_relevant_memories",
        lambda question: memories,
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
    ):
        captured["answer_request"] = {
            "original_question": original_question,
            "research_question": research_question,
            "evidence": evidence,
            "verbose": verbose,
        }
        return "We decided to use evidence rather than guesses."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question(
        "What did we decide about how ALF should answer questions?"
    )

    assert captured["answer_request"] == {
        "original_question": (
            "What did we decide about how ALF should answer questions?"
        ),
        "research_question": (
            "What did we decide about how ALF should answer questions?"
        ),
        "evidence": memories,
        "verbose": False,
    }

    assert result.answer == (
        "We decided to use evidence rather than guesses."
    )
    assert result.source == "memory"
    assert result.research_question is None


def test_answer_question_admits_when_no_memory_matches(monkeypatch):
    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.MEMORY,
    )

    monkeypatch.setattr(
        question,
        "find_relevant_memories",
        lambda question: [],
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *arguments, **kwargs: pytest.fail(
            "ALF must not answer without memory evidence"
        ),
    )

    result = question.answer_question(
        "What did we decide about something forgotten?"
    )

    assert result.answer == (
        "I couldn't find any relevant memories about that. "
        "I don't want to guess."
    )
    assert result.source is None
    assert result.research_question is None


def test_answer_question_declines_unsupported_question(monkeypatch):
    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.DECLINE,
    )

    monkeypatch.setattr(
        question,
        "interpret_question",
        lambda question: pytest.fail(
            "Declined questions must not be interpreted"
        ),
    )

    monkeypatch.setattr(
        question,
        "research_web",
        lambda question: pytest.fail(
            "Declined questions must not research the web"
        ),
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *arguments, **kwargs: pytest.fail(
            "Declined questions must not be passed to the LLM"
        ),
    )

    result = question.answer_question(
        "Can you make me a cup of tea?"
    )

    assert result.answer == "I can't help with that."
    assert result.source is None
    assert result.research_question is None


def make_news_items():
    base = {
        "id": 1,
        "subject": "Ukraine",
        "feed_title": "https://feeds.example/ukraine.rss",
        "title": "Ukraine economy shows strong growth",
        "url": "https://feeds.example/n/1",
        "summary": "",
        "published_at": "2026-08-27T10:00:00Z",
        "first_seen_at": "2026-08-27T10:01:00",
        "matched_terms": ["economy"],
        "content": None,
    }

    return [
        base,
        {
            **base,
            "id": 2,
            "title": "Ukraine plans a redesign",
            "url": "https://feeds.example/n/2",
            "matched_terms": ["economy", "redesign"],
        },
    ]


def make_news_intent():
    return NewsIntent(
        topics=("economy", "redesign"),
        window=NewsWindow(None, None, None),
        original="What has happened in Ukraine recently?",
    )
