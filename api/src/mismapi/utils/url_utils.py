from collections.abc import Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def merge_query_params(url: str, extra: Mapping[str, str]) -> str:
    """Merge ``extra`` params into ``url``'s query string, preserving fragment.

    Correctly handles:

    - absolute URLs (``https://app.example.com/home``) and relative paths
      (``/api/auth/login``);
    - hash-routed SPA URIs where the fragment must not swallow the new query
      (``https://app.example.com/#/home`` → ``...?...#/home``);
    - URIs with a pre-existing query string, whose params are preserved and
      merged with ``extra`` (duplicate keys are kept, as allowed by RFC 3986);
    - URIs with a trailing ``?`` or other edge cases that naive
      ``f"{url}?{urlencode(extra)}"`` concatenation mishandles;
    - values containing reserved characters (``&``, ``=``, ``%``, ``#``,
      spaces, unicode), which are percent-encoded via :func:`urlencode`.

    Note that :func:`parse_qsl` + :func:`urlencode` round-tripping canonicalizes
    encoding (e.g., space becomes ``+``). Do not use this helper when the
    caller requires byte-for-byte preservation of the original query string.
    """
    parsed = urlparse(url)
    merged = parse_qsl(parsed.query, keep_blank_values=True) + list(extra.items())
    return urlunparse(parsed._replace(query=urlencode(merged)))
