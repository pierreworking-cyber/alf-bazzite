
import pytest

from alf.assessment import should_assess
from alf.routes import Route


@pytest.mark.parametrize(
    "question",
    [
        "What does pytest -q mean?",
        "Translate hello into French.",
        "What is a Python list?",
        "Write a short thank-you note.",
        "Reply with exactly one word: OK",
    ],
)
def test_simple_llm_questions_do_not_require_assessment(question):
    assert should_assess(question, Route.LLM) is False


@pytest.mark.parametrize(
    "question",
    [
        "How do I replace my operating system?",
        "Give me the terminal commands to configure SSH.",
        "My computer keeps crashing. How do I diagnose the problem?",
        "Write a Python script to organise these files.",
        "Compare these two approaches and explain their disadvantages.",
        "Explain how to configure the network and troubleshoot connection failures.",
        "My laptop won't boot. What should I check?",
        "What are the risks of changing my disk partitions?",
        "Review this Python function and find any errors.",
    ],
)
def test_substantial_llm_questions_require_assessment(question):
    assert should_assess(question, Route.LLM) is True


@pytest.mark.parametrize(
    "route",
    [
        Route.SYSTEM,
        Route.MEMORY,
        Route.RESEARCH,
    ],
)
def test_evidence_based_routes_require_assessment(route):
    assert should_assess("A straightforward question.", route) is True


def test_decline_route_does_not_require_assessment():
    assert should_assess("Can you make me a cup of tea?", Route.DECLINE) is False

