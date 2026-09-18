"""
ALF path management.

Defines where ALF stores its runtime data.
"""

from pathlib import Path


def get_data_directory():
    """
    Return ALF's data directory.
    """

    return Path.home() / ".local" / "share" / "alf"
