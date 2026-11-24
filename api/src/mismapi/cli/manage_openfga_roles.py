"""Grant or revoke MISM-291 platform-wide OpenFGA roles.

OpenFGA has no built-in admin UI, so this is the operational surface for
managing the four platform-wide roles that gate the Administrator Approval
Gate for Execution Environments (MISM-291): ``uploader``, ``upload_reviewer``,
``image_checker``, ``executor``. All four are relations on the singleton
``platform:main`` object — see Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md.

Reads OpenFGA connection settings from the same environment variables the API
itself uses (``OPENFGA_API_URL``, ``OPENFGA_STORE_ID``,
``OPENFGA_AUTHORIZATION_MODEL_ID``), so it talks to the same store the
running deployment does.

Usage::

    uv run mism-manage-openfga-roles grant --role uploader --user alice
    uv run mism-manage-openfga-roles revoke --role executor --user bob

``--user`` takes the bare subject id (the JWT ``sub`` claim / OIDC subject) —
the script adds the ``user:`` tuple prefix itself.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.core.settings import get_settings

#: The four platform-wide roles defined on the `platform` type
#: (Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md). Kept in sync with that schema by
#: hand — there is no runtime introspection of the deployed OpenFGA model.
VALID_ROLES: tuple[str, ...] = ("uploader", "upload_reviewer", "image_checker", "executor")

#: Every platform role is a relation on this singleton object.
PLATFORM_OBJECT = "platform:main"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mism-manage-openfga-roles",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action, verb in (("grant", "Grant"), ("revoke", "Revoke")):
        sub = subparsers.add_parser(action, help=f"{verb} a platform role")
        sub.add_argument(
            "--role",
            required=True,
            choices=VALID_ROLES,
            help="Platform role to modify.",
        )
        sub.add_argument(
            "--user",
            required=True,
            help="Subject id (the JWT 'sub' claim), without the 'user:' tuple prefix.",
        )

    return parser


async def _run(action: str, role: str, user_subject: str) -> None:
    settings = get_settings()
    client = OpenFGAClient(
        base_url=settings.openfga_api_url,
        store_id=settings.openfga_store_id,
        authorization_model_id=settings.openfga_authorization_model_id,
        timeout_seconds=settings.openfga_timeout_seconds,
    )
    user = f"user:{user_subject}"
    try:
        if action == "grant":
            await client.write_tuple(user=user, relation=role, object_=PLATFORM_OBJECT)
            print(f"Granted '{role}' to {user} on {PLATFORM_OBJECT}.")
        else:
            await client.delete_tuple(user=user, relation=role, object_=PLATFORM_OBJECT)
            print(f"Revoked '{role}' from {user} on {PLATFORM_OBJECT}.")
    finally:
        await client.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        asyncio.run(_run(args.action, args.role, args.user))
    except APIError as exc:
        print(
            f"Error: {exc.detail} (code={exc.code}, status={exc.status_code})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
