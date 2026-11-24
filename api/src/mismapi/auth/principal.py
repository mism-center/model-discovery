"""
Dependency-free authentication principal value type.

`AuthenticatedPrincipal` lives here (rather than in
`mismapi.auth.validator` or `mismapi.auth.base`) so validator
implementations can import it without pulling in any validator class or
request-path glue. The validator protocol (`AuthValidator`) and the OIDC
validator (`OIDCAuthValidator`) live in `mismapi.auth.validator`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AuthenticatedPrincipal:
    subject: str
    issuer: str
    audience: str
    scopes: set[str]
