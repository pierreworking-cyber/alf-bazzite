import sys

from alf import commands, main


def test_run_resolves_short_command_prefix(monkeypatch):
    captured = {}

    def fake_remember_command(*arguments):
        captured["arguments"] = arguments

    monkeypatch.setitem(
        commands.command_handlers,
        "remember",
        fake_remember_command,
    )

    assert commands.run("rem", ["note", "Dave is fictional"]) is True

    assert captured["arguments"] == (
        "note",
        "Dave is fictional",
    )


def test_run_resolves_longer_command_prefix(monkeypatch):
    captured = {}

    def fake_remember_command(*arguments):
        captured["arguments"] = arguments

    monkeypatch.setitem(
        commands.command_handlers,
        "remember",
        fake_remember_command,
    )

    assert commands.run("reme", ["note", "Dave is fictional"]) is True

    assert captured["arguments"] == (
        "note",
        "Dave is fictional",
    )


def test_run_rejects_unknown_natural_language_command():
    assert commands.run("make", ["a", "memory", "Dave is fictional"]) is False


def test_run_resolves_category_alias(monkeypatch):
    captured = {}

    def fake_remember_command(*arguments):
        captured["arguments"] = arguments

    monkeypatch.setitem(
        commands.command_handlers,
        "remember",
        fake_remember_command,
    )

    assert commands.run(
        "rem",
        ["notes", "Dave is fictional"],
    ) is True

    assert captured["arguments"] == (
        "notes",
        "Dave is fictional",
    )


def test_run_rejects_unknown_command():
    assert commands.run(
        "make",
        ["a", "memory"],
    ) is False


def test_remember_command_resolves_category_prefix(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "get_memory_types",
        lambda: ["note", "fact", "decision", "preference"],
    )

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(
        commands,
        "remember",
        fake_remember,
    )

    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    commands.remember_command(
        "notes",
        "Dave is fictional",
    )

    assert captured["category"] == "note"
    assert captured["content"] == "Dave is fictional"
    assert captured["related_memory_ids"] is None
    assert captured["saved"] == "note"


def test_remember_command_rejects_unknown_category(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "get_memory_types",
        lambda: ["note", "fact", "decision", "preference"],
    )

    monkeypatch.setattr(
        commands,
        "render_invalid_memory_category",
        lambda category, categories: output.append(
            (category, categories)
        ),
    )

    commands.remember_command(
        "banana",
        "Dave is fictional",
    )

    assert output == [
        (
            "banana",
            ["note", "fact", "decision", "preference"],
        )
    ]


def test_run_resolves_command_and_category_together(monkeypatch):
    captured = {}

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(
        commands,
        "remember",
        fake_remember,
    )

    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    assert commands.run(
        "reme",
        ["notes", "Dave is fictional"],
    ) is True

    assert captured["category"] == "note"
    assert captured["content"] == "Dave is fictional"
    assert captured["related_memory_ids"] is None
    assert captured["saved"] == "note"


def test_remember_accepts_positional_category_and_long_related_option(monkeypatch):
    captured = {}

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(commands, "remember", fake_remember)
    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    assert commands.run(
        "rem",
        ["notes", "Dave is fictional", "--relate", "41"],
    ) is True

    assert captured["category"] == "note"
    assert captured["content"] == "Dave is fictional"
    assert captured["related_memory_ids"] == "41"


def test_remember_accepts_option_category_and_short_related_option(monkeypatch):
    captured = {}

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(commands, "remember", fake_remember)
    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    assert commands.run(
        "rem",
        ["-c", "note", "Dave is fictional", "-r", "41"],
    ) is True

    assert captured["category"] == "note"
    assert captured["content"] == "Dave is fictional"
    assert captured["related_memory_ids"] == "41"


def test_remember_accepts_long_category_option(monkeypatch):
    captured = {}

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(commands, "remember", fake_remember)
    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    assert commands.run(
        "rem",
        ["--category", "note", "Dave is fictional"],
    ) is True

    assert captured["category"] == "note"
    assert captured["content"] == "Dave is fictional"
    assert captured["related_memory_ids"] is None


def test_remember_accepts_content_before_long_category_option(monkeypatch):
    captured = {}

    def fake_remember(category, content, related_memory_ids=None):
        captured["category"] = category
        captured["content"] = content
        captured["related_memory_ids"] = related_memory_ids
        return True

    monkeypatch.setattr(commands, "remember", fake_remember)
    monkeypatch.setattr(
        commands,
        "render_memory_saved",
        lambda category: captured.setdefault("saved", category),
    )

    assert commands.run(
        "rem",
        ["Peter prefers dogs", "--category", "preference"],
    ) is True

    assert captured["category"] == "preference"
    assert captured["content"] == "Peter prefers dogs"
    assert captured["related_memory_ids"] is None


def test_remember_rejects_category_option_without_value(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    assert commands.run(
        "rem",
        ["--category"],
    ) is True

    assert output == ["remember"]


def test_remember_rejects_related_option_without_value(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    assert commands.run(
        "rem",
        ["note", "Dave is fictional", "--relate"],
    ) is True

    assert output == ["remember"]


def test_remember_rejects_unknown_option(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    assert commands.run(
        "rem",
        ["note", "Dave is fictional", "--banana"],
    ) is True

    assert output == ["remember"]


def test_remember_rejects_duplicate_category_specification(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    assert commands.run(
        "rem",
        ["note", "Dave is fictional", "--category", "fact"],
    ) is True

    assert output == ["remember"]


def test_remember_rejects_category_option_without_content(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    assert commands.run(
        "rem",
        ["--category", "note"],
    ) is True

    assert output == ["remember"]


def test_memories_accepts_short_category_option(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "get_memories",
        lambda options: captured.setdefault("options", options) or [],
    )
    monkeypatch.setattr(
        commands,
        "render_memories",
        lambda memories, options: None,
    )

    commands.memories_command(
        "-c",
        "pref",
    )

    assert captured["options"]["category"] == "preference"


def test_search_accepts_short_category_option(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "search_memories",
        lambda term, options: captured.setdefault("options", options) or [],
    )
    monkeypatch.setattr(
        commands,
        "render_memories",
        lambda memories, options: None,
    )

    commands.search_command(
        "Peter",
        "-c",
        "pref",
    )

    assert captured["options"]["category"] == "preference"


def test_search_accepts_options_before_term(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "search_memories",
        lambda term, options: captured.setdefault(
            "arguments",
            (term, options),
        ) or [],
    )
    monkeypatch.setattr(
        commands,
        "render_memories",
        lambda memories, options: None,
    )

    commands.search_command(
        "-c",
        "pref",
        "Peter",
    )

    assert captured["arguments"][0] == "Peter"
    assert captured["arguments"][1]["category"] == "preference"


def test_memories_accepts_short_all_option(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "get_memories",
        lambda options: captured.setdefault("options", options) or [],
    )
    monkeypatch.setattr(
        commands,
        "render_memories",
        lambda memories, options: None,
    )

    commands.memories_command("-a")

    assert captured["options"]["include_archived"] is True


def test_memories_accepts_short_group_option(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        commands,
        "get_memories",
        lambda options: captured.setdefault("options", options) or [],
    )
    monkeypatch.setattr(
        commands,
        "render_memories",
        lambda memories, options: None,
    )

    commands.memories_command(
        "-g",
        "category",
    )

    assert captured["options"]["group"] == "category"


def test_memories_rejects_unknown_short_category_option(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_invalid_memory_category",
        lambda category, categories: output.append(
            (category, categories)
        ),
    )

    commands.memories_command(
        "-c",
        "banana",
    )

    assert output == [
        (
            "banana",
            ["note", "fact", "decision", "preference"],
        )
    ]


def test_search_option_error_points_to_search(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.search_command(
        "Peter",
        "--category",
    )

    assert output == ["search"]


def test_search_rejects_unknown_short_category_option(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_invalid_memory_category",
        lambda category, categories: output.append(
            (category, categories)
        ),
    )

    commands.search_command(
        "Peter",
        "-c",
        "banana",
    )

    assert output == [
        (
            "banana",
            ["note", "fact", "decision", "preference"],
        )
    ]


def test_relate_command_accepts_source_and_target_ids(monkeypatch):
    captured = {}

    def fake_relate_memory(memory_id, related_memory_ids):
        captured["memory_id"] = memory_id
        captured["related_memory_ids"] = related_memory_ids
        return "46"

    monkeypatch.setattr(
        commands,
        "relate_memory",
        fake_relate_memory,
    )

    monkeypatch.setattr(
        commands,
        "render_memory_related",
        lambda memory_id, related_memory_ids: captured.setdefault(
            "rendered",
            (memory_id, related_memory_ids),
        ),
    )

    commands.relate_command(
        "47",
        "46",
    )

    assert captured["memory_id"] == 47
    assert captured["related_memory_ids"] == "46"
    assert captured["rendered"] == (47, "46")


def test_relate_command_rejects_missing_arguments(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_memory_usage",
        lambda usage: output.append(usage),
    )

    commands.relate_command("47")

    assert output == [
        commands.commands["relate"]["usage"],
    ]


def test_relate_command_rejects_non_numeric_source(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_memory_not_numeric",
        lambda: output.append(True),
    )

    commands.relate_command(
        "banana",
        "46",
    )

    assert output == [True]


def test_run_resolves_relate_command(monkeypatch):
    captured = {}

    def fake_relate_command(*arguments):
        captured["arguments"] = arguments

    monkeypatch.setitem(
        commands.command_handlers,
        "relate",
        fake_relate_command,
    )

    assert commands.run(
        "rel",
        ["47", "46"],
    ) is True

    assert captured["arguments"] == (
        "47",
        "46",
    )


def test_calc_command_defaults_to_numeric_with_three_places(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: captured.setdefault("result", result),
    )

    commands.calc_command("12", "*", "7")

    assert captured["arguments"] == ("12 * 7", False, 3, "radians")
    assert captured["result"] == 42


def test_calc_command_accepts_symbolic_option(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("x^2", "--symbolic")

    assert captured["arguments"] == ("x^2", True, 3, "radians")


def test_calc_command_accepts_symbolic_prefix(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("x^2", "--sym")

    assert captured["arguments"] == ("x^2", True, 3, "radians")


def test_calc_command_accepts_degrees_option(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("sin(90)", "--degrees")

    assert captured["arguments"] == (
        "sin(90)",
        False,
        3,
        "degrees",
    )


def test_calc_command_accepts_degrees_prefix(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("sin(90)", "--deg")

    assert captured["arguments"] == (
        "sin(90)",
        False,
        3,
        "degrees",
    )


def test_calc_command_accepts_radians_prefix(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("sin(pi / 2)", "--rad")

    assert captured["arguments"] == (
        "sin(pi / 2)",
        False,
        3,
        "radians",
    )


def test_calc_command_rejects_both_angle_modes(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.calc_command(
        "sin(90)",
        "--degrees",
        "--radians",
    )

    assert output == ["calc"]


def test_calc_command_accepts_places_prefix(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("sqrt(2)", "--pla", "5")

    assert captured["arguments"] == ("sqrt(2)", False, 5, "radians")


def test_calc_command_accepts_places_option(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("sqrt(2)", "--places", "5")

    assert captured["arguments"] == ("sqrt(2)", False, 5, "radians")


def test_calc_command_accepts_leading_negative_expression(monkeypatch):
    captured = {}

    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command("-5 + 3")

    assert captured["arguments"] == ("-5 + 3", False, 3, "radians")


def test_calc_command_options_are_order_independent(monkeypatch):
    captured = {}
    def fake_calculate(
        expression,
        symbolic=False,
        places=3,
        angle_mode="radians",
    ):
        captured["arguments"] = (
            expression,
            symbolic,
            places,
            angle_mode,
        )
        return 42

    monkeypatch.setattr(commands, "calculate", fake_calculate)
    monkeypatch.setattr(
        commands,
        "render_calculation",
        lambda result: None,
    )

    commands.calc_command(
        "--places",
        "5",
        "sqrt(2)",
    )

    assert captured["arguments"] == ("sqrt(2)", False, 5, "radians")


def test_calc_command_rejects_symbolic_with_places(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.calc_command(
        "x^2",
        "--symbolic",
        "--places",
        "5",
    )

    assert output == ["calc"]


def test_calc_command_rejects_places_outside_range(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.calc_command(
        "sqrt(2)",
        "--places",
        "11",
    )

    assert output == ["calc"]


def test_calc_command_rejects_non_numeric_places(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.calc_command(
        "sqrt(2)",
        "--places",
        "banana",
    )

    assert output == ["calc"]


def test_calc_command_rejects_unknown_option(monkeypatch):
    output = []

    monkeypatch.setattr(
        commands,
        "render_command_structure_error",
        lambda command: output.append(command),
    )

    commands.calc_command(
        "sqrt(2)",
        "--banana",
    )

    assert output == ["calc"]


def test_ambiguous_command_is_reported(monkeypatch):
    output = []

    monkeypatch.setattr(
        main,
        "render_ambiguous_command",
        lambda command, matches: output.append((command, matches)),
    )

    monkeypatch.setattr(
        main,
        "run",
        lambda command, arguments: False,
    )

    monkeypatch.setattr(
        main,
        "get_command_matches",
        lambda command: ["memories", "memory"],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["alf", "memor"],
    )

    main.main()

    assert output == [
        ("memor", ["memories", "memory"]),
    ]


def test_ambiguous_command_reports_similar_commands(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["alf", "memor"],
    )

    main.main()

    output = capsys.readouterr().out

    assert "Ambiguous command: memor." in output
    assert "Similar options: alf memories, alf memory" in output
