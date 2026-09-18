from alf.classifier import classify
from alf.routes import Route


def test_classify_system_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt: "system",
    )

    assert classify("What operating system am I running?") == Route.SYSTEM


def test_classify_memory_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt: "memory",
    )

    assert classify("What did we decide about SearXNG?") == Route.MEMORY


def test_classify_research_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt: "research",
    )

    assert classify("What is the latest version of Python?") == Route.RESEARCH


def test_classify_general_knowledge_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt: "llm",
    )

    assert classify("What does pytest -q mean?") == Route.LLM


def test_classify_unsupported_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt: "decline",
    )

    assert classify("Can ALF make me a cup of tea?") == Route.DECLINE


def test_classification_prompt_contains_safety_examples(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "decline"

    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        fake_generate,
    )

    classify("What operating system am I running, and how do I delete it?")

    assert "How do I delete my operating system?" in captured["prompt"]
    assert (
        "What operating system am I running, and how do I delete it?"
        in captured["prompt"]
    )
