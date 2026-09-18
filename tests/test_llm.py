import json

from alf import llm


def test_check_ollama_when_service_and_model_are_available(monkeypatch):
    response_data = {
        "models": [
            {"name": "gemma3:12b"},
            {"name": "some-other-model"},
        ],
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    monkeypatch.setattr(
        llm,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    result = llm.check_ollama()

    assert result == {
        "available": True,
        "model_available": True,
        "model": "gemma3:12b",
        "error": None,
    }


def test_check_ollama_when_model_is_missing(monkeypatch):
    response_data = {
        "models": [
            {"name": "some-other-model"},
        ],
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    monkeypatch.setattr(
        llm,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    result = llm.check_ollama()

    assert result == {
        "available": True,
        "model_available": False,
        "model": "gemma3:12b",
        "error": None,
    }


def test_check_ollama_when_service_is_unavailable(monkeypatch):
    def fake_urlopen(request, timeout):
        raise OSError("Connection refused")

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.check_ollama()

    assert result["available"] is False
    assert result["model_available"] is False
    assert result["model"] == "gemma3:12b"
    assert result["error"] == "Connection refused"


def test_ask_returns_ollama_response(monkeypatch):
    response_data = {
        "response": "The answer from Ollama.",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.ask(
        {
            "question": "What is the capital of France?",
            "evidence": [
                {
                    "source": "web",
                    "title": "France",
                    "text": "France is a country in Europe.",
                }
            ],
        }
    )

    assert result == "The answer from Ollama."


def test_ask_handles_no_research(monkeypatch):
    response_data = {
        "response": "An answer without research.",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.ask(
        {
            "question": "What is 2 + 2?",
            "evidence": [],
        }
    )

    assert result == "An answer without research."


def test_ask_requires_answers_to_stay_within_evidence(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "I don't have enough evidence to answer that."

    monkeypatch.setattr(
        llm,
        "generate",
        fake_generate,
    )

    result = llm.ask(
        {
            "question": "What did we decide about penguin mating habits?",
            "evidence": [
                {
                    "source": "memory",
                    "content": "ALF should use evidence rather than guesses.",
                }
            ],
        }
    )

    assert (
        "The supplied evidence is authoritative for this answer."
        in captured["prompt"]
    )
    assert (
        "Do not fill gaps with your own knowledge."
        in captured["prompt"]
    )
    assert result == "I don't have enough evidence to answer that."


def test_ask_uses_detailed_style_when_verbose(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "A detailed answer."

    monkeypatch.setattr(
        llm,
        "generate",
        fake_generate,
    )

    result = llm.ask(
        {
            "question": "What are microbes?",
            "evidence": [],
            "verbose": True,
        }
    )

    assert "Give a detailed, well-developed answer." in captured["prompt"]
    assert (
        "Provide useful context and explanation rather than a brief response."
        in captured["prompt"]
    )
    assert result == "A detailed answer."


def test_ask_uses_concise_style_when_not_verbose(monkeypatch):
    captured = {}

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return "A concise answer."

    monkeypatch.setattr(
        llm,
        "generate",
        fake_generate,
    )

    result = llm.ask(
        {
            "question": "What are microbes?",
            "evidence": [],
            "verbose": False,
        }
    )

    assert "Give a concise but useful answer." in captured["prompt"]
    assert "Do not add unnecessary detail." in captured["prompt"]
    assert result == "A concise answer."


def test_evaluate_research_returns_relevant_result(monkeypatch):
    response_data = {
        "response": json.dumps(
            {
                "relevant": True,
                "candidates": [1],
                "reason": "The article directly describes the subject in the question.",
            }
        )
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.evaluate_research(
        "What is the capital of France?",
        [
            {
                "source": "web",
                "title": "France",
                "text": "France is a country in Europe. Its capital is Paris.",
            }
        ],
    )

    assert result == {
        "relevant": True,
        "candidates": [1],
        "reason": "The article directly describes the subject in the question.",
    }


def test_evaluate_research_returns_not_relevant_result(monkeypatch):
    response_data = {
        "response": json.dumps(
            {
                "relevant": False,
                "candidates": [],
                "reason": "The supplied articles do not match the question.",
            }
        )
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.evaluate_research(
        "What film featured children mistaking a homeless man for Jesus?",
        [
            {
                "source": "web",
                "title": "Whitney Houston",
                "text": "Whitney Houston was an American singer and actress.",
            }
        ],
    )

    assert result == {
        "relevant": False,
        "candidates": [],
        "reason": "The supplied articles do not match the question.",
    }


def test_evaluate_research_rejects_invalid_response(monkeypatch):
    response_data = {
        "response": "This is not JSON.",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    try:
        llm.evaluate_research(
            "What is the capital of France?",
            [
                {
                    "source": "web",
                    "title": "France",
                    "text": "France is a country in Europe.",
                }
            ],
        )
    except ValueError as error:
        assert str(error) == "Invalid research evaluation response"
    else:
        raise AssertionError("Expected ValueError")
