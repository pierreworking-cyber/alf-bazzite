from alf import interpretation


def test_interpret_question_returns_llm_response(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return (
            "Why are trailing commas commonly used in multi-line "
            "Python function calls and definitions?"
        )

    monkeypatch.setattr(
        interpretation,
        "generate",
        fake_generate,
    )

    result = interpretation.interpret_question(
        'Why do some Python function structures terminate elements with "," '
        "and some do not?"
    )

    assert result == (
        "Why are trailing commas commonly used in multi-line "
        "Python function calls and definitions?"
    )

    assert (
        'Why do some Python function structures terminate elements with "," '
        "and some do not?"
    ) in captured["prompt"]

    assert "Do not answer the question." in captured["prompt"]
    assert "Preserve the meaning of the user's question." in captured["prompt"]


def test_interpret_question_allows_already_suitable_question(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "What are microbes?"

    monkeypatch.setattr(
        interpretation,
        "generate",
        fake_generate,
    )

    result = interpretation.interpret_question(
        "What are microbes?"
    )

    assert result == "What are microbes?"

    assert "If the question is already clear and suitable for research" in (
        captured["prompt"]
    )

    assert "Preserve useful and specific terminology already present" in (
        captured["prompt"]
    )
    assert (
        "If the question is already clear and suitable for research, return it"
        in captured["prompt"]
    )
    assert "unchanged." in captured["prompt"]


def test_interpret_question_preserves_searchable_question(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "What is the difference between a Python tuple and a list?"

    monkeypatch.setattr(
        interpretation,
        "generate",
        fake_generate,
    )

    question = "What is the difference between a Python tuple and a list?"

    result = interpretation.interpret_question(question)

    assert result == question
    assert question in captured["prompt"]


def test_interpret_question_does_not_answer_question(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "What is the difference between a Python tuple and a list?"

    monkeypatch.setattr(
        interpretation,
        "generate",
        fake_generate,
    )

    result = interpretation.interpret_question(
        "How is a Python tuple different from a list?"
    )

    assert result == "What is the difference between a Python tuple and a list?"
    assert "Do not answer the question." in captured["prompt"]


def test_interpret_question_clarifies_misspelled_title(monkeypatch):
    monkeypatch.setattr(
        interpretation,
        "generate",
        lambda prompt: "Who wrote The Moon's a Balloon?",
    )

    result = interpretation.interpret_question(
        "who wrote the moons a ballon"
    )

    assert result == "Who wrote The Moon's a Balloon?"
