"""
News query data structures and text helpers for ALF.
"""

import re
from dataclasses import dataclass
from datetime import datetime

NEWS_DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 366

_TOPIC_STOP_WORDS = frozenset(
    """
    a about after again against all am an and any are around as at
    be been being before but by can could did do does doing for from
    had has have having how i if in into is it its just may might more
    most my of off on only or our over shall should so some than that
    the their them then there these they this those through to under us
    was we were what when where which who whom why will with would you
    your been latest recent recently today yesterday last past previous
    ago news headline headlines happened happening happen happens
    occurred going on story stories said say says told update updates
    announced announcement coverage discussed discuss reporting report
    reports reported current week weeks day days hour hours month months
    year years monday tuesday wednesday thursday friday saturday sunday
    january february march april may june july august september october
    november december progress progressed progressing developments
    development up to doing
    """.split()
)

@dataclass(frozen=True)
class NewsWindow:
    """
    A News time window.

    Attributes:
        start: The inclusive window start, or ``None`` when open-ended.
        end: The inclusive window end, or ``None`` when open-ended.
        days: The window length in whole days for display, or ``None``
            when the window is not a whole number of days.
    """

    start: datetime | None
    end: datetime | None
    days: int | None


@dataclass(frozen=True)
class NewsIntent:
    """
    Structured News query information.

    Attributes:
        topics: The significant topic terms, in order.
        window: The requested time window.
        original: The original query text.
    """

    topics: tuple[str, ...]
    window: NewsWindow
    original: str


def normalize_text(text):
    """
    Normalise text for topic matching.

    Text is lowercased and apostrophes are stripped so possessives such
    as "Alzheimer's" match their stems ("alzheimers").
    """

    return text.lower().replace("'", "").replace("’", "")


def topic_terms(text):
    """
    Return the significant topic terms from a phrase.

    Terms are normalised, lowercased, and filtered for stop words and
    request vocabulary. At most four terms are returned.

    Args:
        text: The phrase to extract topic terms from.

    Returns:
        A tuple of topic terms in order of appearance.
    """

    terms = []
    seen = set()

    for token in re.findall(r"[a-z0-9]+", normalize_text(text)):
        if token.isdigit() or token in _TOPIC_STOP_WORDS:
            continue

        if token in seen:
            continue

        seen.add(token)
        terms.append(token)

        if len(terms) == 4:
            break

    return tuple(terms)
