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


def test_answer_question_uses_general_knowledge_when_no_research_is_found(
    monkeypatch,
):
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

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
        research_judgement=None,
        research_unavailable=False,
    ):
        captured["evidence"] = evidence
        captured["research_judgement"] = research_judgement
        captured["research_unavailable"] = research_unavailable
        return "An answer based on general knowledge."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question("What film is this?")

    assert captured["evidence"] == []
    assert captured["research_unavailable"] is True
    assert "no usable evidence" in captured["research_judgement"]

    assert result.answer == "An answer based on general knowledge."
    assert result.source == "llm"
    assert result.research_question == "What film is this?"


def test_answer_question_passes_selected_research_evidence(
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

    evaluation = {
        "answer": "Both sources support the answer.",
        "confidence": "high",
        "supporting_candidates": [1, 2],
        "rejected_candidates": [],
        "reason": "Both sources provide direct support.",
    }

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
        "evaluate_evidence",
        lambda question, candidates: evaluation,
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
        research_judgement=None,
        research_unavailable=False,
        evidence_type="none",
    ):

        captured["evidence"] = evidence
        captured["research_judgement"] = research_judgement
        captured["research_unavailable"] = research_unavailable
        captured["evidence_type"] = evidence_type
        return "Answer from both sources."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question("What happened?")

    assert captured["evidence"] == candidates
    assert "Both sources support the answer." in captured["research_judgement"]
    assert "Confidence: high" in captured["research_judgement"]
    assert captured["research_unavailable"] is False
    assert captured["evidence_type"] == "research"
    assert result.answer == "Answer from both sources."
    assert result.source == "web"
    assert result.research_question == "What happened?"


def test_answer_question_falls_back_when_research_confidence_is_low(
    monkeypatch,
):
    candidates = [
        {
            "title": "Weak source",
            "url": "https://example.com/weak",
            "text": "A weakly supported claim.",
        },
    ]

    evaluation = {
        "answer": "A tentative conclusion.",
        "confidence": "low",
        "supporting_candidates": [1],
        "rejected_candidates": [],
        "reason": "The evidence is inconclusive.",
    }

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
        "evaluate_evidence",
        lambda question, candidates: evaluation,
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
        research_judgement=None,
        research_unavailable=False,
    ):
        captured["evidence"] = evidence
        captured["research_judgement"] = research_judgement
        captured["research_unavailable"] = research_unavailable
        return "An answer based on general knowledge."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question("What happened?")

    assert captured["evidence"] == []
    assert captured["research_unavailable"] is True
    assert "low-confidence support" in captured["research_judgement"]
    assert "A tentative conclusion" not in captured["research_judgement"]

    assert result.answer == "An answer based on general knowledge."
    assert result.source == "llm"
    assert result.research_question == "What happened?"


def test_answer_question_falls_back_when_evidence_evaluation_fails(
    monkeypatch,
):
    candidates = [
        {
            "title": "Unreviewed source",
            "url": "https://example.com/unreviewed",
            "text": "Unreviewed evidence.",
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

    def failed_evaluation(question, candidates):
        raise RuntimeError("Evidence evaluation failed")

    monkeypatch.setattr(
        question,
        "evaluate_evidence",
        failed_evaluation,
    )

    captured = {}

    def fake_prepare_answer(
        original_question,
        research_question,
        evidence,
        verbose=False,
        research_judgement=None,
        research_unavailable=False,
    ):
        captured["evidence"] = evidence
        captured["research_judgement"] = research_judgement
        captured["research_unavailable"] = research_unavailable
        return "An answer without verified web evidence."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    result = question.answer_question("What happened?")

    assert captured["evidence"] == []
    assert captured["research_unavailable"] is True
    assert "evidence review failed" in captured["research_judgement"]

    assert result.answer == "An answer without verified web evidence."
    assert result.source == "llm"
    assert result.research_question == "What happened?"


def test_answer_question_does_not_retry_when_fallback_answering_fails(
    monkeypatch,
):
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

    calls = 0

    def failed_prepare_answer(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("Answer generation failed")

    monkeypatch.setattr(
        question,
        "prepare_answer",
        failed_prepare_answer,
    )

    with pytest.raises(
        RuntimeError,
        match="Answer generation failed",
    ):
        question.answer_question("What happened?")

    assert calls == 1


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
        evidence_type="none",
    ):
        captured["answer_request"] = {
            "original_question": original_question,
            "research_question": research_question,
            "evidence": evidence,
            "verbose": verbose,
            "evidence_type": evidence_type,
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
        "evidence_type": "system",
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
        evidence_type="none",
    ):
        captured["answer_request"] = {
            "original_question": original_question,
            "research_question": research_question,
            "evidence": evidence,
            "verbose": verbose,
            "evidence_type": evidence_type,
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
        "evidence_type": "memory",
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


def test_answer_question_assesses_substantial_llm_answer(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.LLM,
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *args, **kwargs: (
            "Use the terminal to inspect the configuration."
        ),
    )

    def fake_should_assess(original_question, selected_route):
        return True

    def fake_evaluate_answer(
        question,
        answer,
        route,
        evidence,
        research_judgement=None,
        research_unavailable=False,
    ):
        captured["assessment"] = {
            "question": question,
            "answer": answer,
            "route": route,
            "evidence": evidence,
            "research_judgement": research_judgement,
            "research_unavailable": research_unavailable,
        }

        return {
            "verdict": "ACCEPT",
            "issues": [],
            "correction": "",
            "reason": "The answer is correct.",
        }

    monkeypatch.setattr(
        question,
        "should_assess",
        fake_should_assess,
        raising=False,
    )

    monkeypatch.setattr(
        question,
        "evaluate_answer",
        fake_evaluate_answer,
        raising=False,
    )

    original_question = "How do I inspect the configuration?"

    result = question.answer_question(original_question)

    assert captured["assessment"] == {
        "question": original_question,
        "answer": "Use the terminal to inspect the configuration.",
        "route": "LLM",
        "evidence": [],
        "research_judgement": None,
        "research_unavailable": False,
    }

    assert result.answer == (
        "Use the terminal to inspect the configuration."
    )
    assert result.source == "llm"
    assert result.research_question is None


def test_answer_question_revises_answer_when_assessment_requests_it(
    monkeypatch,
):
    prepare_calls = []
    assessment_calls = []

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.LLM,
    )

    monkeypatch.setattr(
        question,
        "should_assess",
        lambda original_question, selected_route: True,
    )

    def fake_prepare_answer(*args, **kwargs):
        prepare_calls.append((args, kwargs))

        if len(prepare_calls) == 1:
            return "The original answer."

        return "The corrected answer."

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    def fake_evaluate_answer(**kwargs):
        assessment_calls.append(kwargs)

        if len(assessment_calls) == 1:
            return {
                "verdict": "REVISE",
                "issues": ["The original answer is incomplete."],
                "correction": (
                    "Explain that the command only displays the "
                    "configuration; it does not change it."
                ),
                "reason": "The answer needs clarification.",
            }

        return {
            "verdict": "ACCEPT",
            "issues": [],
            "correction": "",
            "reason": "The corrected answer is satisfactory.",
        }

    monkeypatch.setattr(
        question,
        "evaluate_answer",
        fake_evaluate_answer,
    )

    original_question = "How do I inspect the configuration?"

    result = question.answer_question(original_question)

    assert len(prepare_calls) == 2
    assert len(assessment_calls) == 2

    assert prepare_calls[1][1]["assessment_correction"] == (
        "Explain that the command only displays the "
        "configuration; it does not change it."
    )

    assert result.answer == "The corrected answer."
    assert result.source == "llm"



@pytest.mark.parametrize(
    "second_verdict",
    ["REVISE", "RESEARCH", "UNRESOLVED"],
)
def test_answer_question_handles_second_assessment_verdict(
    monkeypatch,
    second_verdict,
):
    assessment_calls = []
    prepare_calls = []
    research_calls = []

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.LLM,
    )
    monkeypatch.setattr(
        question,
        "should_assess",
        lambda original_question, selected_route: True,
    )

    def fake_prepare_answer(*args, **kwargs):
        prepare_calls.append(kwargs)
        return (
            "The original answer."
            if len(prepare_calls) == 1
            else "The corrected answer."
        )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        fake_prepare_answer,
    )

    def fake_evaluate_answer(**kwargs):
        assessment_calls.append(kwargs)

        if len(assessment_calls) == 1:
            return {
                "verdict": "REVISE",
                "issues": ["The original answer is incomplete."],
                "correction": "Clarify the technical distinction.",
                "reason": "The answer needs correction.",
            }

        return {
            "verdict": second_verdict,
            "issues": ["A further issue remains."],
            "correction": "A further correction is required.",
            "reason": "The revised answer remains uncertain.",
        }

    monkeypatch.setattr(
        question,
        "evaluate_answer",
        fake_evaluate_answer,
    )

    def fake_research_answer(
        original_question,
        research_query,
        verbose,
        report,
        fallback_answer=None,
    ):
        research_calls.append({
            "original_question": original_question,
            "research_query": research_query,
            "fallback_answer": fallback_answer,
        })
        return question.QuestionResult(
            answer="The research-supported answer.",
            source="web",
            research_question=research_query,
        )

    monkeypatch.setattr(
        question,
        "research_answer",
        fake_research_answer,
    )

    original_question = "How do I inspect the configuration?"

    result = question.answer_question(original_question)

    assert len(prepare_calls) == 2
    assert len(assessment_calls) == 2

    if second_verdict == "REVISE":
        assert result.answer.startswith("The corrected answer.")
        assert "could not establish" in result.answer.lower()
        assert "A further correction is required." in result.answer
        assert research_calls == []

    elif second_verdict == "RESEARCH":
        assert result.answer == "The research-supported answer."
        assert result.source == "web"
        assert len(research_calls) == 1
        assert research_calls[0]["fallback_answer"] == (
            "The corrected answer."
        )

    elif second_verdict == "UNRESOLVED":
        assert result.answer.startswith("The corrected answer.")
        assert "could not establish" in result.answer.lower()
        assert "remains uncertain" in result.answer
        assert research_calls == []


def test_answer_question_researches_when_assessment_requests_it(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.LLM,
    )

    monkeypatch.setattr(
        question,
        "should_assess",
        lambda original_question, selected_route: True,
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *args, **kwargs: "The original answer.",
    )

    monkeypatch.setattr(
        question,
        "evaluate_answer",
        lambda **kwargs: {
            "verdict": "RESEARCH",
            "issues": ["A technical detail needs verification."],
            "correction": "Check whether the command is supported on Linux.",
            "reason": "The answer contains an unverified technical claim.",
        },
    )

    def fake_research_answer(
        original_question,
        research_query,
        verbose,
        report,
        fallback_answer=None,
    ):
        captured["original_question"] = original_question
        captured["research_query"] = research_query
        captured["fallback_answer"] = fallback_answer

        return question.QuestionResult(
            answer="The research-supported answer.",
            source="web",
            research_question="Interpreted research query",
        )

    monkeypatch.setattr(
        question,
        "research_answer",
        fake_research_answer,
    )

    original_question = "How do I inspect the configuration?"

    result = question.answer_question(original_question)

    assert captured["original_question"] == original_question
    assert original_question in captured["research_query"]
    assert "Check whether the command is supported on Linux." in (
        captured["research_query"]
    )
    assert captured["fallback_answer"] == "The original answer."

    assert result.answer == "The research-supported answer."
    assert result.source == "web"
    assert result.research_question == "Interpreted research query"


def test_research_answer_retains_original_when_research_fails(monkeypatch):
    monkeypatch.setattr(
        question,
        "interpret_question",
        lambda query: query,
    )

    monkeypatch.setattr(
        question,
        "research_web",
        lambda query: [],
    )

    def unexpected_prepare_answer(*args, **kwargs):
        raise AssertionError(
            "A fallback answer should not be generated."
        )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        unexpected_prepare_answer,
    )

    result = question.research_answer(
        original_question="How do I inspect the configuration?",
        research_query="Check whether this command is supported.",
        verbose=False,
        report=lambda message: None,
        fallback_answer="The original answer.",
    )

    assert "The original answer." in result.answer
    assert "could not verify" in result.answer.lower()
    assert "unverified" in result.answer.lower()
    assert result.source == "llm"


def test_answer_question_qualifies_unresolved_answer(monkeypatch):
    monkeypatch.setattr(
        question,
        "route",
        lambda question: Route.LLM,
    )

    monkeypatch.setattr(
        question,
        "should_assess",
        lambda original_question, selected_route: True,
    )

    monkeypatch.setattr(
        question,
        "prepare_answer",
        lambda *args, **kwargs: "The original answer.",
    )

    monkeypatch.setattr(
        question,
        "evaluate_answer",
        lambda **kwargs: {
            "verdict": "UNRESOLVED",
            "issues": ["A key detail could not be verified."],
            "correction": "",
            "reason": "There is insufficient evidence to establish reliability.",
        },
    )

    result = question.answer_question(
        "How do I inspect the configuration?"
    )

    assert "The original answer." in result.answer
    assert "could not establish" in result.answer.lower()
    assert "reliab" in result.answer.lower()
    assert result.source == "llm"


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
