"""
Deterministic resolution of ALF commands and contextual vocabulary.

This module deliberately performs only small, unambiguous vocabulary
resolution. It does not attempt to infer natural-language intent.
"""

from .command_catalogue import commands
from .memory import get_memory_types


def get_command_matches(value):
    """
    Find commands matching an exact name or leading prefix.

    Matching is case-insensitive and ignores surrounding whitespace.
    An exact command name takes precedence over prefix matching.

    Args:
        value: The command name or prefix to match.

    Returns:
        A list of matching canonical command names. An empty list is
        returned when there are no matches.
    """

    value = value.strip().lower()

    if not value:
        return []

    if value in commands:
        return [value]

    return [
        command
        for command in commands
        if command.startswith(value)
    ]


def resolve_command(value):
    """
    Resolve a command to its canonical name.

    A command may be given by its exact name or by a leading prefix,
    provided that the prefix matches exactly one command. Ambiguous and
    unknown values are deliberately rejected rather than guessed.

    Args:
        value: The command name or prefix to resolve.

    Returns:
        The canonical command name when the value resolves uniquely;
        otherwise ``None``.
    """

    matches = get_command_matches(value)

    if len(matches) == 1:
        return matches[0]

    return None


def resolve_category(value):
    """
    Resolve a memory category to its canonical name.

    Matching is case-insensitive and accepts an exact category name,
    its singular form, or an unambiguous leading prefix.

    Returns:
        The canonical category name when the value resolves uniquely;
        otherwise ``None``.
    """

    value = value.strip().lower()

    categories = get_memory_types()

    if value in categories:
        return value

    if value.endswith("s") and value[:-1] in categories:
        return value[:-1]

    matches = [
        category
        for category in categories
        if category.startswith(value)
    ]

    if len(matches) == 1:
        return matches[0]

    return None


def resolve_option(value, options):
    """
    Resolve an exact option or an unambiguous leading prefix.

    Returns the canonical option name, or None if the value is unknown
    or ambiguous.
    """

    value = value.strip().lower()

    if value in options:
        return value

    matches = [
        option
        for option in options
        if option.startswith(value)
    ]

    if len(matches) == 1:
        return matches[0]

    return None
