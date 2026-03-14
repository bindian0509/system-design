"""Shared yfinance-compatible HTTP session.

yfinance 1.x requires a curl_cffi session. On some macOS / Python 3.14
setups, the bundled libcurl fails SSL certificate verification. This
module provides a pre-configured session that disables strict SSL
verification to work around the issue.
"""

import curl_cffi.requests

_session: curl_cffi.requests.Session | None = None


def get_yf_session() -> curl_cffi.requests.Session:
    global _session
    if _session is None:
        _session = curl_cffi.requests.Session(
            impersonate="chrome",
            verify=False,
        )
    return _session
