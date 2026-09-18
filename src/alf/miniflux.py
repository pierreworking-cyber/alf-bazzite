"""
Miniflux infrastructure boundary for ALF.

This module is ALF's deliberately thin adapter to a Miniflux feed
reader service. It encapsulates HTTP communication with Miniflux and
exposes only the operations required by ALF's future News capability:
configuring a connection, creating and listing the categories and feeds
that back news subjects, refreshing feeds, and retrieving entries.

The module is stateless and knows nothing about ALF's News domain. It
maps the Miniflux REST API onto plain Python calls and translates HTTP,
connection, and parsing failures into ``MinifluxError`` values so that
domain code never deals with transport details, authentication headers,
or URLs.
"""

import json
from http.client import responses
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = "alf-news/0.3.0"

DEFAULT_TIMEOUT = 10.0


class MinifluxError(Exception):
    """
    Raised when ALF cannot communicate with the Miniflux service.
    """


class Miniflux:
    """
    Thin HTTP client for a Miniflux service.

    The client is constructed with the service base URL and an API key
    (the mechanism established for ALF by the Miniflux evaluation) and
    exposes only the operations required by ALF's news subjects. It
    makes no domain decisions; it returns Miniflux's JSON responses as
    parsed Python values.

    An optional ``transport`` callable may be supplied for tests. It
    replaces the network layer and must accept
    ``(method, url, headers, payload, timeout)`` and return a
    ``(status, body)`` tuple. Connection failures are reported by
    raising ``MinifluxError``.
    """

    def __init__(
        self,
        base_url,
        api_key,
        timeout=DEFAULT_TIMEOUT,
        transport=None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport or _default_transport

    def version(self):
        """
        Return Miniflux version information.
        """
        return self._request("GET", "/v1/version")

    def me(self):
        """
        Return the authenticated user, confirming service and API key.

        This is the minimal status check: a successful response proves
        the service is reachable and the API key is accepted.
        """
        return self._request("GET", "/v1/me")

    def get_categories(self):
        """
        Return all Miniflux categories.

        Miniflux returns the categories as a bare JSON array.
        """
        return self._request("GET", "/v1/categories")

    def create_category(self, title):
        """
        Create a category with the given title.
        """
        return self._request(
            "POST",
            "/v1/categories",
            payload={"title": title},
        )

    def update_category(self, category_id, title):
        """
        Rename a Miniflux category.
        """
        return self._request(
            "PUT",
            f"/v1/categories/{category_id}",
            payload={"title": title},
        )

    def delete_category(self, category_id):
        """
        Delete a category and the feeds it contains.
        """
        return self._request(
            "DELETE",
            f"/v1/categories/{category_id}",
        )

    def get_feeds(self, category_id=None):
        """
        Return feeds, optionally restricted to a category.

        Miniflux returns the feeds as a bare JSON array.
        """
        if category_id is None:
            return self._request("GET", "/v1/feeds")

        return self._request(
            "GET",
            f"/v1/categories/{category_id}/feeds",
        )

    def create_feed(self, feed_url, category_id):
        """
        Add a feed to a category and return the created feed.

        Miniflux confirms feed creation with only the new feed's id, so
        the complete feed record is retrieved from the category
        afterwards.
        """
        created = self._request(
            "POST",
            "/v1/feeds",
            payload={
                "feed_url": feed_url,
                "category_id": category_id,
            },
        )

        feed_id = created["feed_id"]

        for feed in self.get_feeds(category_id=category_id):
            if feed["id"] == feed_id:
                return feed

        raise MinifluxError(
            f"The created feed could not be retrieved: {feed_url}"
        )

    def delete_feed(self, feed_id):
        """
        Delete a feed from Miniflux.
        """
        return self._request(
            "DELETE",
            f"/v1/feeds/{feed_id}",
        )

    def update_feed(self, feed_id, category_id):
        """
        Move an existing feed to another category.
        """
        return self._request(
            "PUT",
            f"/v1/feeds/{feed_id}",
            payload={"category_id": category_id},
        )

    def refresh_feed(self, feed_id):
        """
        Ask Miniflux to refresh a feed now.

        The refresh is synchronous; Miniflux returns an empty response.
        Newly discovered entries are retrieved with ``get_entries``.
        """
        self._request("PUT", f"/v1/feeds/{feed_id}/refresh")

    def get_entries(
        self,
        category_id=None,
        feed_id=None,
        published_after=None,
        published_before=None,
        limit=100,
        offset=0,
        status=None,
    ):
        """
        Return a page of entries, newest first, optionally filtered.

        ``feed_id`` optionally restricts results to one Miniflux feed.
        ``published_after`` and ``published_before`` are unix timestamps
        as accepted by the Miniflux API. ``status`` may contain entry
        statuses such as ``read`` or ``unread``.
        Results are capped by Miniflux at 100 entries per page.
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        if category_id is not None:
            params["category_id"] = category_id

        if feed_id is not None:
            params["feed_id"] = feed_id

        if published_after is not None:
            params["published_after"] = published_after

        if published_before is not None:
            params["published_before"] = published_before

        if status is not None:
            params["status"] = status

        data = self._request(
            "GET",
            "/v1/entries",
            params=params,
        )

        return data.get("entries", [])

    def _request(self, method, path, params=None, payload=None):
        url = self._base_url + path

        if params:
            url = f"{url}?{urlencode(sorted(params.items()))}"

        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "X-Auth-Token": self._api_key,
        }

        if payload is not None:
            headers["Content-Type"] = "application/json"

        status, body = self._transport(
            method,
            url,
            headers,
            payload,
            self._timeout,
        )

        return _parse_response(status, body)


def _parse_response(status, body):
    """
    Convert a status and response body into a Python value.
    """
    if 200 <= status < 300:
        if not body:
            return None

        try:
            return json.loads(body)
        except ValueError as error:
            raise MinifluxError(
                f"Miniflux returned an invalid response (HTTP {status})."
            ) from error

    raise MinifluxError(_error_message(status, body))


def _error_message(status, body):
    """
    Build a readable error message from an unsuccessful response.
    """
    reason = responses.get(status)
    message = f"Miniflux error {status}"

    if reason:
        message = f"{message} ({reason})"

    if body:
        try:
            detail = json.loads(body).get("error_message")
        except ValueError:
            detail = None

        if detail:
            message = f"{message}: {detail}"

    return message


def _default_transport(method, url, headers, payload, timeout):
    """
    Perform an HTTP request using the standard library.
    """
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except URLError as error:
        raise MinifluxError(
            f"Could not connect to Miniflux at {_service_url(url)}: "
            f"{_connection_reason(error.reason)}"
        ) from error


def _service_url(url):
    """
    Return the scheme and host portion of a service request URL.

    User-facing connection errors mention the configured service, not
    the internal API endpoint being requested.
    """
    parts = urlsplit(url)

    return f"{parts.scheme}://{parts.netloc}"


def _connection_reason(reason):
    """
    Return a readable reason for an underlying connection failure.
    """
    if isinstance(reason, OSError) and reason.strerror:
        return reason.strerror

    if reason:
        return str(reason)

    return "connection failed"
