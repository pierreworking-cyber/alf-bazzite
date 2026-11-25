import json
import pytest
from alf import llm

MODEL = llm.OLLAMA_MODEL

def test_generate_preserves_default_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps({"response": "OK"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.generate("Return OK.")

    assert result == "OK"
    assert captured["payload"] == {
        "model": MODEL,
        "prompt": "Return OK.",
        "stream": False,
    }
    assert captured["timeout"] == 180


def test_generate_accepts_task_specific_options(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps({"response": "system"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.generate(
        "Classify this question.",
        think=False,
        options={"num_predict": 16},
    )

    assert result == "system"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"] == {"num_predict": 16}


def test_generate_json_requests_json_format(monkeypatch):
    captured = {}

    response_data = {
        "response": '{"answer": "Paris"}',
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.generate_json("Return JSON.")

    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["model"] == MODEL
    assert captured["timeout"] == 180
    assert result == {"answer": "Paris"}


def test_generate_json_rejects_invalid_json(monkeypatch):
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

    monkeypatch.setattr(
        llm,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    with pytest.raises(json.JSONDecodeError):
        llm.generate_json("Return JSON.")


def test_check_ollama_when_service_and_model_are_available(monkeypatch):
    response_data = {
        "models": [
            {"name": MODEL},
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
        "model": MODEL,
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
        "model": MODEL,
        "error": None,
    }


def test_check_ollama_when_service_is_unavailable(monkeypatch):
    def fake_urlopen(request, timeout):
        raise OSError("Connection refused")

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.check_ollama()

    assert result["available"] is False
    assert result["model_available"] is False
    assert result["model"] == MODEL
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
                    "url": "https://example.com/france",
                    "domain": "example.com",
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

    def fake_generate(prompt, **kwargs):
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
            "evidence_type": "research",
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


def test_ask_includes_research_judgement(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "The supported answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    result = llm.ask(
        {
            "question": "What does the research establish?",
            "evidence": [
                {
                    "source": "web",
                    "content": "The evidence supports the conclusion.",
                }
            ],
            "research_judgement": (
                "The evidence strongly supports the conclusion."
            ),
            "evidence_type": "research",
        }
    )

    assert "Research judgement:" in captured["prompt"]
    assert (
        "The evidence strongly supports the conclusion."
        in captured["prompt"]
    )
    assert (
        "The research judgement is the authoritative conclusion"
        in captured["prompt"]
    )
    assert result == "The supported answer."


def test_ask_uses_memory_as_context_without_restricting_general_knowledge(
    monkeypatch,
):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "A memory-based answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    result = llm.ask(
        {
            "question": "What did we decide about ALF?",
            "evidence": [
                {
                    "source": "memory",
                    "content": "ALF should prioritise correctness over speed.",
                }
            ],
            "evidence_type": "memory",
        }
    )

    assert "retrieved memories from previous conversations" in (
        captured["prompt"]
    )
    assert "Use it as the source for claims" in captured["prompt"]
    assert "Do not invent missing details" in captured["prompt"]
    assert "You may use general knowledge" in captured["prompt"]
    assert result == "A memory-based answer."


def test_ask_uses_system_information_as_context(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "A system-aware answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    result = llm.ask(
        {
            "question": "How can I make better use of my GPU?",
            "evidence": [
                {
                    "source": "system",
                    "content": "GPU: AMD Radeon RX 9070.",
                }
            ],
            "evidence_type": "system",
        }
    )

    assert "actual computer on which ALF is running" in (
        captured["prompt"]
    )
    assert "Treat those machine details as factual context" in (
        captured["prompt"]
    )
    assert "general knowledge and reasoning" in captured["prompt"]
    assert "Do not invent machine details" in captured["prompt"]
    assert result == "A system-aware answer."


def test_ask_allows_general_knowledge_when_research_unavailable(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "A knowledge-based answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    result = llm.ask(
        {
            "question": "Explain how rainbows form.",
            "evidence": [],
            "research_unavailable": True,
        }
    )

    assert "Live research was unavailable" in captured["prompt"]
    assert "general language-model knowledge" in captured["prompt"]
    assert "Do not claim that the answer has been externally verified." in (
        captured["prompt"]
    )
    assert "Do not refuse merely because live research failed" in (
        captured["prompt"]
    )
    assert result == "A knowledge-based answer."


def test_ask_allows_general_knowledge_for_ordinary_questions(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "An ordinary answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    result = llm.ask(
        {
            "question": "Why is the sky blue?",
            "evidence": [],
        }
    )

    assert "No external evidence was supplied." in captured["prompt"]
    assert "ordinary knowledge or explanatory question" in (
        captured["prompt"]
    )
    assert (
        "Do not pretend that this knowledge has been externally verified."
        in captured["prompt"]
    )

    assert result == "An ordinary answer."


def test_ask_uses_detailed_style_when_verbose(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
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

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
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
    assert captured["kwargs"]["think"] is False
    assert result == "A concise answer."


def test_evaluate_research_includes_source_provenance(monkeypatch):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "relevant": True,
                "candidates": [1],
                "reason": "The source supports the answer.",
            }
        )

    monkeypatch.setattr(
        llm,
        "generate",
        fake_generate,
    )

    llm.evaluate_research(
        "What is the capital of France?",
        [
            {
                "source": "web",
                "title": "France",
                "url": "https://www.gov.uk/world/france",
                "domain": "gov.uk",
                "text": "France is a country in Europe. Its capital is Paris.",
            }
        ],
    )

    assert "URL: https://www.gov.uk/world/france" in captured["prompt"]
    assert "Domain: gov.uk" in captured["prompt"]


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
                "url": "https://example.com/france",
                "domain": "example.com",
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
                "url": "https://example.com/whitney-houston",
                "domain": "example.com",
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
                    "url": "https://example.com/france",
                    "domain": "example.com",
                    "text": "France is a country in Europe.",
                }
            ],
        )
    except ValueError as error:
        assert str(error) == "Invalid research evaluation response"
    else:
        raise AssertionError("Expected ValueError")


def test_ask_includes_assessment_correction_without_weakening_evidence_rules(
    monkeypatch,
):
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return "The revised answer."

    monkeypatch.setattr(llm, "generate", fake_generate)

    correction = (
        "Explain that the command only displays the configuration; "
        "it does not change it."
    )

    result = llm.ask(
        {
            "question": "How do I inspect the configuration?",
            "evidence": [
                {
                    "source": "web",
                    "content": "The command displays the configuration.",
                }
            ],
            "evidence_type": "research",
            "assessment_correction": correction,
        }
    )

    assert correction in captured["prompt"]
    assert "Answer using only the supplied research evidence." in (
        captured["prompt"]
    )
    assert "Do not fill gaps with your own knowledge." in (
        captured["prompt"]
    )
    assert result == "The revised answer."
    assert "You MUST address every issue identified in the feedback." in (
        captured["prompt"]
    )
    assert "Implement the suggested correction in the revised answer" in (
        captured["prompt"]
    )
    assert "Check that the revised answer actually resolves the" in (
        captured["prompt"]
    )

