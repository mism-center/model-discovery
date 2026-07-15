from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine, text

# Test DB is published on the host by docker-compose.test.yaml (5433:5432).
# Override with MISM_TEST_DATABASE_URL when the stack runs elsewhere.
_TEST_DB_URL = os.environ.get(
    "MISM_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/mism_test",
)


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def approve(*resource_ids: str) -> None:
    """Flip resources to registration_status='approved' directly in the test DB.

    Search only surfaces active + approved resources (RegistryService._SEARCH_GATE),
    but the API has no approve endpoint — approval happens on metadata-package save,
    which the lightweight fixtures don't perform. This does the same transition via
    SQL so seeded resources become discoverable by /search.
    """
    if not resource_ids:
        return
    engine = create_engine(_TEST_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE resources SET registration_status = 'approved' WHERE id = ANY(:ids)"),
                {"ids": list(resource_ids)},
            )
    finally:
        engine.dispose()
