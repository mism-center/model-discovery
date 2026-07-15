from fastapi import APIRouter

from mismapi.api.auth import router as auth_router
from mismapi.api.internal import router as internal_router
from mismapi.api.v1.datasets import router as datasets_router
from mismapi.api.v1.github_import import router as github_import_router
from mismapi.api.v1.models import router as models_router
from mismapi.api.v1.resource_files import router as resource_files_router
from mismapi.api.v1.runs import router as runs_router
from mismapi.api.v1.search import router as search_router
from mismapi.api.v1.upload_files import router as upload_files_router
from mismapi.core.settings import get_settings


def build_api_router() -> APIRouter:
    # Prefix is configurable so ingress can put a UI at "/" and the API at "/api".
    api_router = APIRouter(prefix=get_settings().api_prefix)
    v1_router = APIRouter(prefix="/v1")
    v1_router.include_router(models_router, tags=["Models"])
    v1_router.include_router(github_import_router, tags=["Models"])
    v1_router.include_router(datasets_router, tags=["Datasets"])
    v1_router.include_router(runs_router, tags=["Runs"])
    v1_router.include_router(resource_files_router, tags=["Files"])
    v1_router.include_router(search_router, tags=["Search"])
    v1_router.include_router(upload_files_router, tags=["Files"])
    api_router.include_router(auth_router, tags=["Auth"])
    api_router.include_router(v1_router)
    # Internal endpoints (e.g. tusd hooks) sit under /api but NOT under /v1:
    # they are not subject to the v1 router's blanket `require_principal`
    # dependency. The unified tusd hook endpoint (/tusd/hooks) dispatches on
    # the hook event type and applies per-event auth (pre-create: upload
    # token in tus metadata + session store; post-finish: none at app layer).
    api_router.include_router(internal_router)
    return api_router
