"""
ALF time utilities.
"""

from datetime import datetime


def get_greeting():
    hour = datetime.now().hour

    if hour < 12:
        return "Good morning"

    if hour < 18:
        return "Good afternoon"

    return "Good evening"
