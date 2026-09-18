"""
External research for ALF.

Provides a small boundary between ALF and external web information.
"""

import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from .identity import get_identity

MAX_WEB_RESULTS = 10


def prepare_search_query(question):
    """
    Prepare a concise search query from a research question.

    Explicitly quoted phrases are treated as search terms. Questions asking
    who wrote something are searched using the thing being written. Other
    questions are returned unchanged.
    """
    matches = re.findall(r'"([^"]+)"', question)

    if matches:
        return matches[0]

    match = re.match(
        r"^\s*who\s+wrote\s+(.+?)\??\s*$",
        question,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return question


def fetch(url):
    """
    Fetch text content from an external URL.
    """
    identity = get_identity()

    request = Request(
        url,
        headers={"User-Agent": f"{identity['name']}/{identity['version']}/research"},
    )

    with urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8")


def search_web(question):
    """
    Search SearXNG and return a small set of candidate pages.
    """
    url = (
    "http://127.0.0.1:8080/search"
    f"?q={quote(prepare_search_query(question))}&format=json"
    )

    try:
        data = json.loads(fetch(url))
    except OSError:
        return []

    results = []

    for result in data.get("results", [])[:MAX_WEB_RESULTS]:
        title = result.get("title")
        text = result.get("content", "")
        result_url = result.get("url")

        if not title or not result_url:
            continue

        results.append(
            {
                "source": "web",
                "title": title,
                "url": result_url,
                "text": text,
            }
        )

    return results


def research_web(question):
    """
    Search the web and return a small evidence set for evaluation.
    """

    results = search_web(question)

    candidates = []

    for result in results:
        text = result.get("text", "")

        if not text:
            continue

        candidates.append(
            {
                "source": "web",
                "title": result["title"],
                "url": result["url"],
                "text": text,
            }
        )

    return candidates


