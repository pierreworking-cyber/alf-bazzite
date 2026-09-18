#!/usr/bin/env python3

"""
ALF application entry point.

Handles command-line startup, command resolution, help requests, and
the default interactive introduction when no command is supplied.
"""

from .command_resolution import get_command_matches
from .commands import help_command, run, show_status
from .presentation import (
    error,
    info,
    render_ambiguous_command,
    render_greeting,
)
from .time import get_greeting


def introduce():
    """
    Display ALF's greeting and initial status information.

    This is the default startup path when ALF is invoked without a
    command-line command.
    """
    render_greeting(f"{get_greeting()}, Peter.")
    show_status()


def main():
    """
    Process ALF's command-line arguments and dispatch the requested command.

    With a command argument, ``main()`` handles help requests and passes
    other commands to the deterministic command dispatcher. Unknown or
    ambiguous commands are reported to the user.

    With no command argument, ALF displays its default introduction.
    """
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] in ("--help", "-h"):
            help_command()
            return

        command = sys.argv[1]
        arguments = sys.argv[2:]
        if run(command, arguments):
            return

        matches = get_command_matches(command)

        if len(matches) > 1:
            render_ambiguous_command(command, matches)
            return

        error(f"Unknown command: {command}")
        info("Try: alf help")
        return

    introduce()


if __name__ == "__main__":
    main()
