from alf import healthcheck


def test_check_llm_service_when_ollama_and_model_are_available(monkeypatch):
    monkeypatch.setattr(
        healthcheck,
        "check_ollama",
        lambda: {
            "available": True,
            "model_available": True,
            "model": "gemma3:12b",
            "error": None,
        },
    )

    result = healthcheck.check_llm_service()

    assert result == {
        "name": "Ollama",
        "healthy": True,
        "details": {
            "service_available": True,
            "model": "gemma3:12b",
            "model_available": True,
            "error": None,
        },
    }


def test_check_llm_service_when_model_is_missing(monkeypatch):
    monkeypatch.setattr(
        healthcheck,
        "check_ollama",
        lambda: {
            "available": True,
            "model_available": False,
            "model": "gemma3:12b",
            "error": None,
        },
    )

    result = healthcheck.check_llm_service()

    assert result == {
        "name": "Ollama",
        "healthy": False,
        "details": {
            "service_available": True,
            "model": "gemma3:12b",
            "model_available": False,
            "error": None,
        },
    }


def test_check_llm_service_when_ollama_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        healthcheck,
        "check_ollama",
        lambda: {
            "available": False,
            "model_available": False,
            "model": "gemma3:12b",
            "error": "Connection refused",
        },
    )

    result = healthcheck.check_llm_service()

    assert result == {
        "name": "Ollama",
        "healthy": False,
        "details": {
            "service_available": False,
            "model": "gemma3:12b",
            "model_available": False,
            "error": "Connection refused",
        },
    }


def test_health_report_includes_ollama(monkeypatch):
    monkeypatch.setattr(
        healthcheck,
        "check_ollama",
        lambda: {
            "available": True,
            "model_available": True,
            "model": "gemma3:12b",
            "error": None,
        },
    )

    report = healthcheck.get_health_report()

    ollama_check = next(
        check for check in report["checks"]
        if check["name"] == "Ollama"
    )

    assert ollama_check["healthy"] is True
    assert ollama_check["details"]["model"] == "gemma3:12b"
