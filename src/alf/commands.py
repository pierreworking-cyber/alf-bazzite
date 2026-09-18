"""
Command dispatch and command handling for ALF.

This module resolves user-facing commands to their handlers, validates
command arguments, invokes the appropriate ALF functionality, and passes
results to the presentation layer.

Command routing is deterministic: command names and unambiguous prefixes
are resolved explicitly rather than interpreted as natural-language intent.
"""

from datetime import UTC, datetime, timedelta

from .calc import CalculationError, calculate
from .command_catalogue import commands
from .command_resolution import resolve_category, resolve_command, resolve_option
from .healthcheck import get_health_report
from .identity import get_about_information, get_identity
from .memory import (
    archive_memories,
    delete_memories,
    get_memories,
    get_memory,
    get_memory_categories,
    get_memory_history,
    get_memory_query_options,
    get_memory_types,
    get_related_memories,
    relate_memory,
    remember,
    search_memories,
)
from .miniflux import MinifluxError
from .news import (
    NEWS_QUERY_LIMIT,
    NewsError,
    NewsQuery,
    add_subject,
    get_news_config,
    get_news_status,
    list_subjects,
    query_items,
    refresh,
)
from .news_intent import (
    MAX_WINDOW_DAYS,
    NEWS_DEFAULT_WINDOW_DAYS,
    topic_terms,
)
from .presentation import (
    error,
    render_about,
    render_calculation,
    render_calculation_error,
    render_command_help,
    render_command_structure_error,
    render_commands,
    render_health,
    render_invalid_memory_category,
    render_invalid_related_memory,
    render_memories,
    render_memories_archived,
    render_memories_deleted,
    render_memory,
    render_memory_archived,
    render_memory_categories,
    render_memory_deleted,
    render_memory_history,
    render_memory_missing,
    render_memory_not_numeric,
    render_memory_positive,
    render_memory_related,
    render_memory_saved,
    render_memory_usage,
    render_news_error,
    render_news_query,
    render_news_refreshed,
    render_news_status,
    render_news_subject_added,
    render_news_subjects,
    render_question,
    render_status,
    render_version,
)
from .question import answer_question
from .status import get_status_information


def run(command: str, arguments=None):
    """
    Resolve and execute a user-facing ALF command.

    Command resolution accepts exact names and unambiguous leading
    prefixes. Natural-language intent is never inferred. Unknown or
    ambiguous commands are rejected without invoking a handler.

    Args:
        command: The command name or unambiguous prefix.
        arguments: Optional arguments passed to the command handler.

    Returns:
        ``True`` when the command was resolved and executed; otherwise
        ``False``.
    """

    command = resolve_command(command)

    if command is None:
        return False

    if arguments:
        command_handlers[command](*arguments)
    else:
        command_handlers[command]()

    return True


def calc_command(*arguments):
    """
    Handle the ``calc`` command.

    Parses calculator options, evaluates the requested mathematical
    expression, and passes the result or an appropriate error to the
    presentation layer.

    Args:
        *arguments: Command-line arguments supplied after ``calc``.
    """

    if not arguments:
        render_command_help("calc", commands["calc"])
        return

    expression_arguments = []
    symbolic = False
    places = 3
    angle_mode = "radians"
    index = 0

    options = {
        "--symbolic": "--symbolic",
        "--places": "--places",
        "--degrees": "--degrees",
        "--radians": "--radians",
    }

    while index < len(arguments):
        argument = arguments[index]

        if argument.startswith("-"):
            option = resolve_option(argument, options)

            if option is None:
                if argument.startswith("--"):
                    render_command_structure_error("calc")
                    return

                expression_arguments.append(argument)
                index += 1
                continue

            if option == "--symbolic":
                if symbolic:
                    render_command_structure_error("calc")
                    return

                symbolic = True
                index += 1
                continue

            if option in {"--degrees", "--radians"}:
                if angle_mode != "radians":
                    render_command_structure_error("calc")
                    return

                angle_mode = option.removeprefix("--")
                index += 1
                continue

            if index + 1 >= len(arguments):
                render_command_structure_error("calc")
                return

            try:
                places = int(arguments[index + 1])
            except ValueError:
                render_command_structure_error("calc")
                return

            if not 1 <= places <= 10:
                render_command_structure_error("calc")
                return

            index += 2
            continue

        expression_arguments.append(argument)
        index += 1

    if not expression_arguments:
        render_command_structure_error("calc")
        return

    if symbolic and places != 3:
        render_command_structure_error("calc")
        return

    expression = " ".join(expression_arguments)

    try:
        result = calculate(
            expression,
            symbolic=symbolic,
            places=places,
            angle_mode=angle_mode,
        )
    except CalculationError as error:
        render_calculation_error(error, expression)
        return

    render_calculation(result)


def health_command(argument=None):
    render_health(
        get_health_report(),
        show_details=argument == "--details",
    )


def show_status():
    render_status(get_status_information())


def help_command(argument=None):
    if argument and argument in commands:
        render_command_help(argument, commands[argument])
        return

    render_commands(get_commands())


def remember_command(*arguments):
    category = None
    related_memory_ids = None
    positional_arguments = []
    index = 0

    while index < len(arguments):
        argument = arguments[index]

        if argument in ("-c", "--category"):
            if category is not None or index + 1 >= len(arguments):
                render_command_structure_error("remember")
                return

            category = arguments[index + 1]
            index += 2
            continue

        if argument in ("-r", "--relate"):
            if (
                related_memory_ids is not None
                or index + 1 >= len(arguments)
            ):
                render_command_structure_error("remember")
                return

            related_memory_ids = arguments[index + 1]
            index += 2
            continue

        if argument.startswith("-"):
            render_command_structure_error("remember")
            return

        positional_arguments.append(argument)
        index += 1

    if category is None:
        if len(positional_arguments) != 2:
            render_command_structure_error("remember")
            return

        category, content = positional_arguments

    else:
        if len(positional_arguments) != 1:
            render_command_structure_error("remember")
            return

        content = positional_arguments[0]

    original_category = category
    category = resolve_category(category)

    if category is None:
        render_invalid_memory_category(
            original_category,
            get_memory_types(),
        )
        return

    content = content.strip()

    result = remember(
        category,
        content,
        related_memory_ids=related_memory_ids,
    )

    if result is not True:
        render_invalid_related_memory(
            related_memory_ids,
            commands["remember"]["usage"],
        )
        return

    render_memory_saved(category)


def parse_memory_query_options(arguments, command="memories"):
    options = get_memory_query_options()
    positional_arguments = []

    index = 0

    while index < len(arguments):
        argument = arguments[index]

        if argument in ("-a", "--all"):
            options["include_archived"] = True

        elif argument in ("-c", "--category"):
            index += 1

            if index >= len(arguments):
                render_command_structure_error(command)
                return None

            category = resolve_category(arguments[index])

            if category is None:
                render_invalid_memory_category(
                    arguments[index],
                    get_memory_types(),
                )
                return None

            options["category"] = category

        elif argument in ("-g", "--group"):
            index += 1

            if index >= len(arguments):
                render_command_structure_error(command)
                return None

            options["group"] = arguments[index]

        else:
            positional_arguments.append(argument)

        index += 1

    return options, positional_arguments


def memories_command(*arguments):
    result = parse_memory_query_options(arguments)

    if result is None:
        return

    options, positional_arguments = result

    if positional_arguments:
        render_command_structure_error("memories")
        return

    memories = get_memories(options)

    render_memories(memories, options)


def search_command(*arguments):
    if not arguments:
        render_memory_usage(commands["search"]["usage"])
        return

    result = parse_memory_query_options(
        arguments,
        command="search",
    )

    if result is None:
        return

    options, positional_arguments = result

    if len(positional_arguments) != 1:
        render_command_structure_error("search")
        return

    term = positional_arguments[0]

    memories = search_memories(term, options)

    render_memories(memories, options)


def categories_command(argument=None):
    render_memory_categories(get_memory_categories())


def memory_command(*arguments):

    if len(arguments) != 1:
        render_memory_usage(commands["memory"]["usage"])
        return

    memory_id = arguments[0]

    try:
        memory_id = int(memory_id)

    except ValueError:
        render_memory_not_numeric()
        return

    if memory_id <= 0:
        render_memory_positive()
        return

    memory = get_memory(memory_id)
    related_memories = get_related_memories(memory_id)

    render_memory(
        memory,
        related_memories=related_memories,
    )


def history_command(*arguments):
    if len(arguments) != 1:
        render_memory_usage(commands["history"]["usage"])
        return

    memory_id = arguments[0]

    try:
        memory_id = int(memory_id)

    except ValueError:
        render_memory_not_numeric()
        return

    if memory_id <= 0:
        render_memory_positive()
        return

    history = get_memory_history(memory_id)

    if not history:
        render_memory(None)
        return

    render_memory_history(history)


def relate_command(*arguments):
    if len(arguments) != 2:
        render_memory_usage(commands["relate"]["usage"])
        return

    memory_id, related_memory_selection = arguments

    try:
        memory_id = int(memory_id)
    except ValueError:
        render_memory_not_numeric()
        return

    if memory_id <= 0:
        render_memory_positive()
        return

    related_memory_ids = interpret_memory_selection(
        related_memory_selection
    )

    if related_memory_ids is None:
        render_invalid_related_memory(
            related_memory_selection,
            commands["relate"]["usage"],
        )
        return

    related_memory_ids = ",".join(
        str(memory_id)
        for memory_id in related_memory_ids
    )

    result = relate_memory(
        memory_id,
        related_memory_ids,
    )

    if result is False:
        render_invalid_related_memory(
            related_memory_selection,
            commands["relate"]["usage"],
        )
        return

    render_memory_related(
        memory_id,
        result,
    )


def archive_command(*arguments):
    if not arguments:
        render_command_structure_error("archive")
        return

    memory_ids = interpret_memory_selection(",".join(arguments))

    if memory_ids is None:
        render_command_structure_error("archive")
        return

    result = archive_memories(memory_ids)

    if result["archived"]:
        if len(result["archived"]) == 1:
            render_memory_archived(result["archived"][0])
        else:
            render_memories_archived(result["archived"])

    if result["missing"]:
        render_memory_missing(result["missing"])


def interpret_memory_selection(selection):
    """
    Expand a memory selection into individual memory IDs.

    Selections may contain individual IDs, comma-separated IDs, and
    inclusive ranges. Duplicate IDs are removed while preserving their
    first occurrence.

    Args:
        selection: A memory selection such as ``"10-12,15,20-21"``.

    Returns:
        A list of individual memory IDs, or ``None`` when the selection
        is invalid.
    """

    memory_ids = []

    for part in selection.split(","):
        if not part:
            return None

        if "-" in part:
            bounds = part.split("-")

            if len(bounds) != 2:
                return None

            start, end = bounds

            if not start.isdigit() or not end.isdigit():
                return None

            start = int(start)
            end = int(end)

            if start <= 0 or end <= 0:
                return None

            for memory_id in range(
                min(start, end),
                max(start, end) + 1,
            ):
                if memory_id not in memory_ids:
                    memory_ids.append(memory_id)

        else:
            if not part.isdigit() or int(part) <= 0:
                return None

            memory_id = int(part)

            if memory_id not in memory_ids:
                memory_ids.append(memory_id)

    return memory_ids


def delete_command(*arguments):
    if not arguments:
        render_command_structure_error("delete")
        return

    memory_ids = interpret_memory_selection(",".join(arguments))

    if memory_ids is None:
        render_command_structure_error("delete")
        return

    result = delete_memories(memory_ids)

    if result["deleted"]:
        if len(result["deleted"]) == 1:
            render_memory_deleted(result["deleted"][0])
        else:
            render_memories_deleted(result["deleted"])

    if result["missing"]:
        render_memory_missing(result["missing"])


def question_command(*arguments):
    """
    Handle the ``question`` command.

    Reconstructs the user's question from the command arguments, applies
    the optional verbose flag, sends the question through ALF's question
    engine, and presents the resulting answer.

    Args:
        *arguments: Command-line arguments supplied after ``question``.
    """
    verbose = False
    question_arguments = []

    for argument in arguments:
        if argument in ("-v", "--verbose"):
            verbose = True
            continue

        if argument.startswith("-"):
            render_command_structure_error("question")
            return

        question_arguments.append(argument)

    if not question_arguments:
        render_memory_usage(commands["question"]["usage"])
        return

    original_question = " ".join(question_arguments).strip()

    try:
        result = answer_question(
            original_question,
            verbose=verbose,
        )
    except Exception:
        error("I couldn't get an answer to the question.")
        return

    render_question(
        result.answer,
        result.source,
        result.research_question,
        news_items=result.news_items,
    )


def news_command(*arguments):
    """
    Handle the ``news`` command.

    Routes the first argument to the requested news subcommand and
    validates the subcommand's arguments before invoking ALF's news
    data layer.

    Args:
        *arguments: Command-line arguments supplied after ``news``.
    """

    if not arguments:
        render_command_help("news", commands["news"])
        return

    subcommand = arguments[0]

    handlers = {
        "add": news_add_command,
        "refresh": news_refresh_command,
        "list": news_list_command,
        "query": news_query_command,
        "status": news_status_command,
    }

    handler = handlers.get(subcommand)

    if handler is None:
        render_command_structure_error("news")
        return

    handler(*arguments[1:])


def news_add_command(*arguments):
    """
    Handle the ``news add`` subcommand.

    Registers a news subject and its feed subscriptions.
    """

    if len(arguments) < 2:
        render_command_structure_error("news")
        return

    for argument in arguments:
        if argument.startswith("-"):
            render_command_structure_error("news")
            return

    subject = arguments[0]
    feed_urls = arguments[1:]

    try:
        result = add_subject(subject, feed_urls)
    except (MinifluxError, NewsError) as exc:
        render_news_error(str(exc))
        return

    render_news_subject_added(result)


def news_refresh_command(*arguments):
    """
    Handle the ``news refresh`` subcommand.

    Refreshes the stored feeds, optionally restricted to a subject.
    """

    if len(arguments) > 1:
        render_command_structure_error("news")
        return

    subject = arguments[0] if arguments else None

    try:
        result = refresh(subject)
    except (MinifluxError, NewsError) as exc:
        render_news_error(str(exc))
        return

    render_news_refreshed(result)


def news_list_command(*arguments):
    """
    Handle the ``news list`` subcommand.

    Refreshes all stored news feeds and displays the stored subjects with
    their feed counts, item counts, and the number of new items obtained
    by the refresh.
    """

    if arguments:
        render_command_structure_error("news")
        return

    if get_news_config() is None:
        render_news_error("News is not configured. Run `alf news init`.")
        return

    try:
        result = refresh()
    except (MinifluxError, NewsError) as exc:
        render_news_error(str(exc))
        return

    subjects = list_subjects()
    render_news_subjects(subjects, result)


def news_query_command(*arguments):
    """
    Handle the ``news query`` subcommand.

    Retrieves stored news items matching the query text, optionally
    restricted to a number of days back and a result limit.
    """

    days = None
    limit = None
    positional_arguments = []
    index = 0

    while index < len(arguments):
        argument = arguments[index]

        if argument in ("-d", "--days"):
            if days is not None or index + 1 >= len(arguments):
                render_command_structure_error("news")
                return

            try:
                days = int(arguments[index + 1])
            except ValueError:
                render_command_structure_error("news")
                return

            if days <= 0 or days > MAX_WINDOW_DAYS:
                render_command_structure_error("news")
                return

            index += 2
            continue

        if argument == "--limit":
            if limit is not None or index + 1 >= len(arguments):
                render_command_structure_error("news")
                return

            try:
                limit = int(arguments[index + 1])
            except ValueError:
                render_command_structure_error("news")
                return

            if not 1 <= limit <= 100:
                render_command_structure_error("news")
                return

            index += 2
            continue

        if argument.startswith("-"):
            render_command_structure_error("news")
            return

        positional_arguments.append(argument)
        index += 1

    if not positional_arguments or len(positional_arguments) > 2:
        render_command_structure_error("news")
        return

    if len(positional_arguments) == 1:
        subject = None
        search_text = positional_arguments[0]
    else:
        subject = positional_arguments[0]
        search_text = positional_arguments[1]

    topics = topic_terms(search_text)

    if not topics:
        render_command_structure_error("news")
        return

    if get_news_config() is None:
        render_news_error("News is not configured. Run `alf news init`.")
        return

    try:
        refresh()
    except (MinifluxError, NewsError) as exc:
        render_news_error(str(exc))
        return

    now = datetime.now(UTC)
    start = now - timedelta(days=days or NEWS_DEFAULT_WINDOW_DAYS)

    query = NewsQuery(
        topics=topics,
        subject=subject,
        start=start,
        end=now,
        limit=limit or NEWS_QUERY_LIMIT,
    )

    try:
        items = query_items(query)
    except NewsError as exc:
        render_news_error(str(exc))
        return

    render_news_query(items, query)


def news_status_command(*arguments):
    """
    Handle the ``news status`` subcommand.

    Reports the reachability of the news service and the amount of
    stored news data.
    """

    if arguments:
        render_command_structure_error("news")
        return

    render_news_status(get_news_status())


def tui_command():
    from .tui import main

    main()


def web_command():
    from .web import main

    main()


def about_command(argument=None):

    render_about(
        get_about_information(),
        show_details=argument == "--details",
    )


def version_command(argument=None):
    render_version(get_identity())


# Routing table: maps user-facing command names to their handler functions.
# `run()` uses this table to dispatch each command without knowing
# how the individual command is implemented.
command_handlers = {
    "help": help_command,
    "remember": remember_command,
    "memories": memories_command,
    "categories": categories_command,
    "memory": memory_command,
    "relate": relate_command,
    "history": history_command,
    "health": health_command,
    "about": about_command,
    "archive": archive_command,
    "delete": delete_command,
    "version": version_command,
    "calc": calc_command,
    "search": search_command,
    "question": question_command,
    "news": news_command,
    "tui": tui_command,
    "web": web_command,
}


def get_commands():
    """
    Return a copy of the public ALF command catalogue.

    A copy is returned so callers can inspect or present command
    metadata without modifying the canonical command catalogue.

    Returns:
        A dictionary containing the public metadata for each command.
    """
    catalog = {}

    for name, command in commands.items():
        catalog[name] = command.copy()

    return catalog


def get_capability():
    """
    Return ALF's command-discovery capability information.

    The capability describes the available user-facing commands and
    exposes their catalogue metadata to ALF's capability-discovery
    system.

    Returns:
        A capability dictionary describing ALF's command discovery
        facility.
    """

    return {
        "id": "commands",
        "name": "Command discovery",
        "description": "Reports available ALF commands",
        "details": {
            "commands": get_commands(),
        },
    }
