from fastapi import APIRouter, Depends

from mismapi.api.auth import router as auth_router
from mismapi.api.v1.create import router as create_router
from mismapi.api.v1.execution import router as execution_router
from mismapi.api.v1.search import router as search_router
from mismapi.api.v1.upload_files import router as upload_files_router
from mismapi.auth.base import require_principal


def build_api_router() -> APIRouter:
    api_router = APIRouter(prefix="/api")
    v1_router = APIRouter(prefix="/v1", dependencies=[Depends(require_principal)])
    v1_router.include_router(search_router, tags=["Models"])
    v1_router.include_router(create_router, tags=["Models"])
    v1_router.include_router(execution_router, tags=["Execution"])
    v1_router.include_router(upload_files_router, tags=["Models"])
    api_router.include_router(auth_router, tags=["Auth"])
    api_router.include_router(v1_router)
    return api_router
