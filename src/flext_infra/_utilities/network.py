"""Stdlib HTTP owner: reachability preflight and authenticated text requests."""

from __future__ import annotations

from http import HTTPStatus
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlsplit

from flext_core import p, r

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesNetwork:
    """Own every outbound HTTP exchange of the package through ``http.client``."""

    @staticmethod
    def _connection(url: str, *, timeout_seconds: float) -> HTTPConnection:
        """Open one connection for an ``http``/``https`` URL, or raise."""
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            msg = f"HTTP exchange requires an http(s) URL, got {url!r}"
            raise ValueError(msg)
        connection_type = HTTPSConnection if parts.scheme == "https" else HTTPConnection
        return connection_type(parts.hostname, parts.port, timeout=timeout_seconds)

    @staticmethod
    def endpoint_reachable(url: str, *, timeout_seconds: float) -> p.Result[bool]:
        """Return whether one HEAD request receives any HTTP answer in time.

        A server that answers with an error status (403 from a rate limit, 404)
        is reachable: the network path exists and a later authenticated call
        can succeed. Only a connection failure or a timeout means offline. The
        endpoint must be ``http`` or ``https``; any other scheme is a caller
        defect and raises.
        """
        connection = FlextInfraUtilitiesNetwork._connection(
            url, timeout_seconds=timeout_seconds
        )
        try:
            connection.request("HEAD", urlsplit(url).path or "/")
            connection.getresponse()
        except (HTTPException, OSError) as exc:
            return r[bool].fail(
                f"endpoint {url!r} did not respond: {exc}", exception=exc
            )
        else:
            return r[bool].ok(True)
        finally:
            connection.close()

    @staticmethod
    def http_bearer_text(
        method: str,
        url: str,
        *,
        bearer_token: t.SecretStr,
        form: t.SequenceOf[t.Pair[str, str]],
        timeout_seconds: float,
    ) -> p.Result[str]:
        """Send one bearer-authenticated request and return its 2xx body text.

        ``form`` is the query string of a ``GET`` and the url-encoded body of
        any other method; repeated keys are preserved in order. A non-2xx
        status, a connection failure, or a timeout fails with the status and
        body the server sent. The token travels only in the ``Authorization``
        header and never appears in a failure message.
        """
        connection = FlextInfraUtilitiesNetwork._connection(
            url, timeout_seconds=timeout_seconds
        )
        encoded = urlencode(tuple(form))
        path = urlsplit(url).path or "/"
        headers = {"Authorization": f"Bearer {bearer_token.get_secret_value()}"}
        body: str | None = None
        if method == "GET":
            path = f"{path}?{encoded}" if encoded else path
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = encoded
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            text = response.read().decode("utf-8")
        except (HTTPException, OSError) as exc:
            return r[str].fail(f"{method} {url} did not complete: {exc}", exception=exc)
        finally:
            connection.close()
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            return r[str].fail(
                f"{method} {url} answered HTTP {response.status}: {text.strip()}"
            )
        return r[str].ok(text)


__all__: list[str] = ["FlextInfraUtilitiesNetwork"]
