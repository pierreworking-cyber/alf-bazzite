"""
Git repository awareness.
"""

import subprocess


def run_git_command(arguments):
    """
    Run a Git command safely.

    Returns:
        Command output if successful.
        None if Git fails.
    """

    result = subprocess.run(
        ["git"] + arguments,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def get_git_branch():
    result = run_git_command(["branch", "--show-current"])

    return result if result else "Unavailable"


def get_git_status():
    result = run_git_command(["status", "--porcelain"])

    if result is None:
        return "Unavailable"

    if result:
        return "modified"

    return "clean"


def get_last_commit():
    result = run_git_command(["log", "-1", "--pretty=%s"])

    return result if result else "Unavailable"


def get_git_information():
    """
    Return Git repository information.
    """

    information = {}

    information["branch"] = get_git_branch()
    information["status"] = get_git_status()
    information["last_commit"] = get_last_commit()

    return information


def get_capability():
    """
    Return Git capability information.
    """

    return {
        "id": "git",
        "name": "Git repository awareness",
        "description": "Reports repository state and history",
        "details": get_git_information(),
    }
