from alf.classifier import classify
from alf.routes import Route

def test_classify_system_question(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["kwargs"] = kwargs
        return "system"

    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        fake_generate,
    )

    assert classify("What operating system am I running?") == Route.SYSTEM

    assert captured["kwargs"] == {
        "think": False,
        "options": {"num_predict": 16},
    }


def test_classify_memory_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs :"memory",
    )

    assert classify("What did we decide about SearXNG?") == Route.MEMORY


def test_classify_research_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs : "research",
    )

    assert classify("What is the latest version of Python?") == Route.RESEARCH


def test_classify_general_knowledge_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs : "llm",
    )

    assert classify("What does pytest -q mean?") == Route.LLM


def test_classify_unsupported_question(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs : "decline",
    )

    assert classify("Can ALF make me a cup of tea?") == Route.DECLINE


def test_classification_prompt_contains_safety_examples(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
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

def test_temporal_question_forces_research(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "llm",
    )

    assert classify(
        "Does the current Ollama API support disabling thinking?"
    ) == Route.RESEARCH


def test_latest_question_forces_research(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "llm",
    )

    assert classify(
        "What is the latest version of Python?"
    ) == Route.RESEARCH


def test_temporal_question_overrides_decline(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "decline",
    )

    assert classify(
        "Can you tell me the current UK inflation rate?"
    ) == Route.RESEARCH


def test_current_system_question_preserves_system_route(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "system",
    )

    assert classify(
        "What is my current IP address?"
    ) == Route.SYSTEM


def test_current_memory_question_preserves_memory_route(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "memory",
    )

    assert classify(
        "What is our current agreed approach to ALF?"
    ) == Route.MEMORY


def test_non_temporal_question_keeps_llm_route(monkeypatch):
    monkeypatch.setattr(
        "alf.classifier.llm.generate",
        lambda prompt, **kwargs: "llm",
    )

    assert classify(
        "How does Python virtual environment activation work?"
    ) == Route.LLM
