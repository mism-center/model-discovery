"""Import endpoints for models held in external repositories."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import (
    BioModelsClientDep,
    ExecutionClientDep,
    RegistryServiceDep,
    SettingsDep,
)
from mismapi.services.biomodels_import import import_biomodels_model

router = APIRouter()


class BioModelsImportRequest(BaseModel):
    model_id: str = Field(description="BioModels model id, e.g. 'BIOMD0000000732'.")


class BioModelsImportResponse(BaseModel):
    model_id: str = Field(description="Id of the model created in this registry.")
    registration_status: str
    source_identifier: str = Field(description="The upstream BioModels id.")
    files_extracted: int
    size_bytes: int
    annotation_started: bool = Field(
        description=(
            "False if the import succeeded but the annotation job could not be "
            "started; retry with POST /runs/{model_id}."
        )
    )


@router.post(
    "/imports/biomodels",
    response_model=BioModelsImportResponse,
    status_code=201,
    summary="Import a BioModels model into the registry",
)
async def import_from_biomodels(
    body: BioModelsImportRequest,
    service: RegistryServiceDep,
    biomodels_client: BioModelsClientDep,
    execution_client: ExecutionClientDep,
    settings: SettingsDep,
    principal: AuthenticatedPrincipalDep,
) -> BioModelsImportResponse:
    """Download a BioModels archive, register it as a DRAFT and start annotation.

    Requires authentication: the import spends the deployment's LLM budget by
    firing an annotation job, the same reasoning that gates ``POST /runs/{id}``.

    Responds 409 if the model is already in the registry, with the existing
    model's id in ``error.meta`` so the caller can link to it.
    """
    imported = await import_biomodels_model(
        principal,
        model_id=body.model_id,
        registry=service,
        biomodels=biomodels_client,
        execution=execution_client,
        settings=settings,
    )

    return BioModelsImportResponse(
        model_id=imported.resource.id,
        registration_status=imported.resource.registration_status.value,
        source_identifier=imported.resource.source_identifier,
        files_extracted=imported.files_extracted,
        size_bytes=imported.size_bytes,
        annotation_started=imported.annotation_started,
    )
