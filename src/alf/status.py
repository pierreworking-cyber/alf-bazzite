"""
ALF self-awareness.

Combines information from ALF's various capabilities.
"""

from .git import get_git_information
from .identity import get_identity
from .memory import get_memory_information
from .system import get_system_information


def get_status_information():
    """
    Return ALF status as structured data.
    """

    status = {}

    status["identity"] = get_identity()
    status["system"] = get_system_information()
    status["memory"] = get_memory_information()
    status["git"] = get_git_information()

    return status
