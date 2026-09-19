"""
External research for ALF.

This module retrieves web pages, extracts readable text, and selects
relevant evidence for answer generation.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from rank_bm25 import BM25Okapi
import trafilatura

from .identity import get_identity


MAX_SEARCH_RESULTS = 10
MAX_EVIDENCE_RESULTS = 10
PASSAGE_MAX_WORDS = 120


class ResultParser(HTMLParser):
    """Parse DuckDuckGo HTML search results."""

    def __init__(self):
        super().__init__()
        self.results = []
        self.in_result = False
        self.in_title = False
        self.current = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "div" and "result" in classes:
            self.in_result = True
            self.current = {}

        elif self.in_result and tag == "a" and "result__a" in classes:
            self.in_title = True
            self.current["url"] = attributes.get("href", "")

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_title = False

        elif tag == "div" and self.in_result:
            if self.current.get("title") and self.current.get("url"):
                self.results.append(self.current)

            self.in_result = False

    def handle_data(self, data):
        if self.in_title:
            self.current["title"] = (
                self.current.get("title", "") + data
            ).strip()


def prepare_search_query(question):
    """Prepare a concise search query from a research question."""

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


def domain(url):
    """Return the normalised domain name for a URL."""

    return urlparse(url).netloc.lower().removeprefix("www.")


def resolve_result_url(url):
    """Resolve a DuckDuckGo redirect URL to its destination URL."""

    parsed = urlparse(url)

    if parsed.netloc.lower().removeprefix("www.") != "duckduckgo.com":
        return url

    if parsed.path != "/l/":
        return url

    destination = parse_qs(parsed.query).get("uddg", [])

    if not destination:
        return url

    return unquote(destination[0])


def fetch(url):
    """Fetch text content from an external URL."""

    identity = get_identity()

    request = Request(
        url,
        headers={
            "User-Agent": (
                f"{identity['name']}/{identity['version']}/research"
            ),
        },
    )

    with urlopen(request, timeout=15) as response:
        return response.read()


def search_web(question):
    """Search DuckDuckGo and return candidate result URLs."""

    query = urlencode({"q": prepare_search_query(question)})
    url = f"https://html.duckduckgo.com/html/?{query}"

    try:
        html = fetch(url)
    except OSError:
        return []

    parser = ResultParser()
    parser.feed(html.decode("utf-8", errors="replace"))

    results = []

    for result in parser.results:
        result_url = resolve_result_url(result["url"])

        if domain(result_url) == "duckduckgo.com":
            continue

        results.append(
            {
                "source": "web",
                "title": result["title"],
                "url": result_url,
            }
        )

    return results[:MAX_SEARCH_RESULTS]


def fetch_and_extract(url):
    """Fetch a web page and extract its readable text."""

    html = fetch(url)

    text = trafilatura.extract(
        html,
        url=url,
        favor_precision=True,
    )

    return text or ""


def split_into_passages(text, max_words=PASSAGE_MAX_WORDS):
    """Split extracted text into bounded passages."""

    words = text.split()
    passages = []

    for start in range(0, len(words), max_words):
        passage = " ".join(words[start:start + max_words])

        if passage:
            passages.append(passage)

    return passages


def build_documents(results):
    """Fetch and extract readable text from search results."""

    def fetch_result(result):
        url = result["url"]
        start = time.perf_counter()

        try:
            text = fetch_and_extract(url)
        except Exception:
            elapsed = time.perf_counter() - start

            print(
                f"[research] FETCH FAILED {elapsed:.2f}s {url}",
                flush=True,
            )

            return None

        elapsed = time.perf_counter() - start

        if not text:
            print(
                f"[research] FETCH EMPTY {elapsed:.2f}s {url}",
                flush=True,
            )

            return None

        print(
            f"[research] FETCH OK {elapsed:.2f}s {url}",
            flush=True,
        )

        return {
            "title": result["title"],
            "url": url,
            "domain": domain(url),
            "passages": split_into_passages(text),
        }

    with ThreadPoolExecutor(max_workers=5) as executor:
        documents = list(
            executor.map(fetch_result, results)
        )

    return [
        document
        for document in documents
        if document is not None
    ]


def rank_passages(question, documents):
    """Rank extracted passages by lexical relevance to the question."""

    passages = []

    for document in documents:
        for passage in document["passages"]:
            passages.append(
                {
                    "title": document["title"],
                    "url": document["url"],
                    "domain": document["domain"],
                    "text": passage,
                }
            )

    if not passages:
        return []

    def tokenize(text):
        return re.findall(r"w+", text.lower())

    tokenized = [
        tokenize(passage["text"])
        for passage in passages
    ]

    bm25 = BM25Okapi(tokenized)
    query_tokens = tokenize(question)
    scores = bm25.get_scores(query_tokens)

    ranked_scores = []

    for score, passage, tokens in zip(
        scores,
        passages,
        tokenized,
    ):
        overlap = len(set(query_tokens) & set(tokens))

        adjusted_score = max(
            0.0,
            float(score) + overlap * 0.1,
        )

        ranked_scores.append(
            (
                adjusted_score,
                passage,
            )
        )

    ranked = sorted(
        ranked_scores,
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        {
            **passage,
            "score": float(score),
        }
        for score, passage in ranked
    ]


def build_source_diverse_pool(ranked_passages):
    """Keep relevant evidence from diverse and authoritative sources."""

    selected = []
    seen_domains = set()

    authoritative_domains = {
        "gov.uk",
    }

    for candidate in ranked_passages:
        if candidate["score"] <= 0:
            continue

        if candidate["domain"] not in authoritative_domains:
            continue

        if candidate["domain"] in seen_domains:
            continue

        selected.append(candidate)
        seen_domains.add(candidate["domain"])

    for candidate in ranked_passages:
        if len(selected) >= MAX_EVIDENCE_RESULTS:
            break

        if candidate["score"] <= 0:
            continue

        if candidate["domain"] in seen_domains:
            continue

        selected.append(candidate)
        seen_domains.add(candidate["domain"])

    return selected


def research(question, timings=None):
    """Retrieve and rank web evidence for a question."""

    if timings is None:
        timings = {}

    start = time.perf_counter()
    results = search_web(question)
    timings["search"] = time.perf_counter() - start

    start = time.perf_counter()
    documents = build_documents(results)
    timings["fetch_extract"] = time.perf_counter() - start

    start = time.perf_counter()
    ranked_passages = rank_passages(
        question,
        documents,
    )
    timings["ranking"] = time.perf_counter() - start

    start = time.perf_counter()
    selected = build_source_diverse_pool(ranked_passages)
    timings["diversity"] = time.perf_counter() - start

    return selected


def research_web(question):
    """Search the web and return a small evidence set for evaluation."""

    return research(question)
