import pytest

from alf import commands, llm


def test_question_command_handles_question_engine_error(
    monkeypatch,
    capsys,
):
    def fake_answer_question(original_question, verbose=False):
        raise RuntimeError("Ollama connection failed")

    monkeypatch.setattr(
        commands,
        "answer_question",
        fake_answer_question,
    )

    commands.question_command("What", "is", "Python?")

    output = capsys.readouterr().out

    assert "I couldn't get an answer to the question." in output


def test_question_command_does_not_render_failed_result(
    monkeypatch,
    capsys,
):
    def fake_answer_question(original_question, verbose=False):
        raise RuntimeError("Ollama connection failed")

    monkeypatch.setattr(
        commands,
        "answer_question",
        fake_answer_question,
    )

    monkeypatch.setattr(
        commands,
        "render_question",
        lambda *arguments: pytest.fail(
            "render_question must not be called after an error"
        ),
    )

    commands.question_command("What", "is", "Python?")

    output = capsys.readouterr().out

    assert "I couldn't get an answer to the question." in output


def test_generate_uses_timeout(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return b'{"response": "Hello"}'

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm.generate("Hello")

    assert result == "Hello"
    assert captured["timeout"] == 60


def test_generate_propagates_urlopen_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    with pytest.raises(TimeoutError, match="timed out"):
        llm.generate("Hello")
