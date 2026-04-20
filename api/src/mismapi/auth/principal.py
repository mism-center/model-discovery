"""Pure, dependency-free auth value type.

:class:`AuthenticatedPrincipal` lives here (rather than in
:mod:`mismapi.auth.validator` or :mod:`mismapi.auth.base`) so validator
implementations can import it without pulling in any validator class or
request-path glue. The validator protocols (`AuthValidator`, `OIDCValidator`)
and the stand-alone ``JWTAuthValidator`` live in
:mod:`mismapi.auth.validator`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AuthenticatedPrincipal:
    subject: str
    issuer: str
    audience: str
    scopes: set[str]
