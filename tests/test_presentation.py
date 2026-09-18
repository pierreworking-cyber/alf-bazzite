from alf import presentation


def test_render_command_structure_error(monkeypatch, capsys):
    monkeypatch.setattr(
        presentation,
        "pause",
        lambda: None,
    )

    presentation.render_command_structure_error("remember")

    output = capsys.readouterr().out

    assert "Improper command structure." in output
    assert "See: alf help remember" in output
    assert "Press Return to continue..." in output


def test_pause_ignores_closed_stdin(monkeypatch):
    def raise_eof():
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    presentation.pause()


def test_render_memory_deleted(capsys):
    presentation.render_memory_deleted(12)

    output = capsys.readouterr().out

    assert "Memory 12 deleted." in output


def test_render_memories_deleted(capsys):
    presentation.render_memories_deleted([10, 11, 12])

    output = capsys.readouterr().out

    assert "Memories 10, 11, 12 deleted." in output


def test_render_memory_missing(capsys):
    presentation.render_memory_missing([25, 27])

    output = capsys.readouterr().out

    assert "Memory IDs not found: 25, 27." in output


def test_render_memory_entry_includes_related_memory_ids(capsys):
    presentation.render_memory_entry(
        {
            "id": 58,
            "created": "2026-08-16 03:42:54",
            "category": "note",
            "status": "active",
            "content": "memory links should be displayed against the memory text",
            "related_memory_ids": "46,42",
        }
    )

    output = capsys.readouterr().out

    assert (
        "memory links should be displayed against the memory text (46, 42)"
        in output
    )


def test_render_memory_entry_without_related_memory_ids(capsys):
    presentation.render_memory_entry(
        {
            "id": 58,
            "created": "2026-08-16 03:42:54",
            "category": "note",
            "status": "active",
            "content": "A memory without links.",
            "related_memory_ids": None,
        }
    )

    output = capsys.readouterr().out

    assert "A memory without links." in output
    assert "A memory without links. (" not in output


def test_render_question_includes_source(capsys):
    presentation.render_question(
        "Monkey patching modifies Python code at runtime.",
        "web",
    )

    output = capsys.readouterr().out

    assert "Monkey patching modifies Python code at runtime." in output
    assert "Source: Web" in output


def test_render_question_includes_interpretation_when_different(capsys):
    presentation.render_question(
        "Trailing commas are allowed in Python.",
        "web",
        "Why are trailing commas allowed in Python?",
    )

    output = capsys.readouterr().out

    assert (
        "Question interpreted as: "
        "Why are trailing commas allowed in Python?"
    ) in output
    assert "Trailing commas are allowed in Python." in output


def test_render_question_omits_interpretation_when_unchanged(capsys):
    presentation.render_question(
        "What are microbes?",
        "web",
        "What are microbes?",
    )

    output = capsys.readouterr().out

    assert "Question interpreted as:" not in output
    assert "What are microbes?" in output


def test_render_question_without_source(capsys):
    presentation.render_question(
        "I couldn't find reliable research.",
    )

    output = capsys.readouterr().out

    assert "I couldn't find reliable research." in output
    assert "Source:" not in output


def test_render_question_includes_news_sources(capsys):
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
        },
        {
            "id": 2,
            "subject": "Ukraine",
            "feed_title": "https://feeds.example/ukraine.rss",
            "title": "Ukraine plans a redesign",
            "url": "https://feeds.example/n/2",
            "summary": "",
            "published_at": "2026-08-27T10:00:00Z",
            "first_seen_at": "2026-08-27T10:01:00",
            "matched_terms": ["economy", "redesign"],
            "content": None,
        },
    ]

    presentation.render_question(
        "Ukraine's economy grew strongly last week [1]. "
        "A redesign is planned [2].",
        "news",
        news_items=news_items,
    )

    output = capsys.readouterr().out

    assert "Ukraine's economy grew strongly last week [1]." in output
    assert "Source: News" in output
    assert "Sources" in output
    assert "[1] Ukraine · 27-Aug-2026 10:00 (Example)" in output
    assert "Ukraine economy shows strong growth" in output
    assert "https://feeds.example/n/1" in output
    assert "[2] Ukraine · 27-Aug-2026 10:00 (Example)" in output
    assert "Ukraine plans a redesign" in output
    assert "https://feeds.example/n/2" in output


def test_render_question_omits_news_sources_when_absent(capsys):
    presentation.render_question(
        "Ukraine's economy grew strongly last week.",
        "news",
    )

    output = capsys.readouterr().out

    assert "Ukraine's economy grew strongly last week." in output
    assert "Sources" not in output


def test_render_news_source_without_date_or_label(capsys):
    presentation.render_news_source(
        {
            "id": 1,
            "subject": "Ukraine",
            "feed_title": "",
            "title": "Ukraine economy shows strong growth",
            "url": "https://feeds.example/n/1",
            "summary": "",
            "published_at": None,
            "first_seen_at": "2026-08-27T10:01:00",
            "matched_terms": ["economy"],
            "content": None,
        },
        1,
    )

    output = capsys.readouterr().out

    assert "[1] Ukraine" in output
    assert "Ukraine economy shows strong growth" in output
    assert "https://feeds.example/n/1" in output


def test_render_ambiguous_command(capsys):
    presentation.render_ambiguous_command(
        "memor",
        ["memories", "memory"],
    )

    output = capsys.readouterr().out

    assert "Ambiguous command: memor" in output
    assert "Similar options: alf memories, alf memory" in output

def test_render_health_handles_commands_module_failure(capsys):
    report = {
        "checks": [
            {
                "name": "Modules",
                "healthy": True,
                "details": {
                    "failed_modules": [],
                },
            },
            {
                "name": "Commands",
                "healthy": False,
                "details": {
                    "warnings": [
                        {
                            "message": "Commands module could not be loaded",
                        }
                    ],
                },
            },
            {
                "name": "Ollama",
                "healthy": True,
                "details": {},
            },
        ]
    }

    presentation.render_health(report)

    output = capsys.readouterr().out

    assert "Command integrity issues:" in output
    assert "- Commands" in output
    assert "Commands module could not be loaded" in output
