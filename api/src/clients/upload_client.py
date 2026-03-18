import logging
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, StringConstraints, ValidationError

from core.errors import APIError
from core.http_client import error_from_downstream_response
from schemas.common import CustomMetadata, ModelId, generate_model_id

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UploadSession:
    upload_id: str
    tracking_id: str


@dataclass(slots=True)
class ModelMetadataUpsertResult:
    model_id: str
    tracking_id: str | None


@dataclass(slots=True)
class ModelUpsertPayload:
    name: str
    description: str | None
    version: str | None
    metadata: CustomMetadata
    model_id: str | None = None


class ModelUpsertResponse(BaseModel):
    model_id: ModelId
    tracking_id: str | None = None


type NonEmptyTrimmedString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UploadInitResponse(BaseModel):
    upload_id: NonEmptyTrimmedString
    tracking_id: NonEmptyTrimmedString


class UploadServiceClient:
    def __init__(self, base_url: str, timeout_seconds: float, stub_upstream: bool = False) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._stub_upstream = stub_upstream

    async def create_model(
        self,
        name: str,
        description: str | None,
        version: str | None,
        metadata: CustomMetadata,
    ) -> ModelMetadataUpsertResult:
        payload = ModelUpsertPayload(
            name=name,
            description=description,
            version=version,
            metadata=metadata,
        )
        return await self._upsert_model(method="post", payload=payload)

    async def update_model(
        self,
        model_id: str,
        name: str,
        description: str | None,
        version: str | None,
        metadata: CustomMetadata,
    ) -> ModelMetadataUpsertResult:
        payload = ModelUpsertPayload(
            model_id=model_id,
            name=name,
            description=description,
            version=version,
            metadata=metadata,
        )
        return await self._upsert_model(method="put", payload=payload)

    async def _upsert_model(
        self,
        method: Literal["post", "put"],
        payload: ModelUpsertPayload,
    ) -> ModelMetadataUpsertResult:
        if self._stub_upstream:
            logger.info("Called upload service (stub) method=%s endpoint=/models", method)
            model_id = payload.model_id if payload.model_id is not None else generate_model_id()
            tracking_id = f"stub-track-{uuid4().hex[:8]}"
            return ModelMetadataUpsertResult(model_id=model_id, tracking_id=tracking_id)

        request_payload: dict[str, str | CustomMetadata | None] = {
            "name": payload.name,
            "description": payload.description,
            "version": payload.version,
            "metadata": payload.metadata,
        }
        if payload.model_id is not None:
            request_payload["model_id"] = payload.model_id

        try:
            response = await self._client.request(
                method=method,
                url="/models",
                json=request_payload,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="model_upsert_timeout",
                detail="Model metadata upsert timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="model_upsert_failed",
                fallback_detail="Model metadata upsert failed.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="model_upsert_failed",
                detail="Model metadata upsert failed.",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise APIError(
                status_code=502,
                code="model_upsert_invalid",
                detail="Model metadata upsert response is invalid.",
            ) from exc

        try:
            parsed = ModelUpsertResponse.model_validate(payload)
        except ValidationError as exc:
            raise APIError(
                status_code=502,
                code="model_upsert_invalid",
                detail="Model metadata upsert response is invalid.",
            ) from exc
        return ModelMetadataUpsertResult(model_id=parsed.model_id, tracking_id=parsed.tracking_id)

    async def init_upload(
        self,
        model_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        if self._stub_upstream:
            logger.info(
                "Called upload service (stub) action=init_upload model_id=%s filename=%s",
                model_id,
                filename,
            )
            return UploadSession(
                upload_id=f"stub-upload-{uuid4().hex[:8]}",
                tracking_id=f"stub-track-{uuid4().hex[:8]}",
            )

        payload = {"filename": filename, "content_type": content_type}
        try:
            response = await self._client.post(f"/models/{model_id}/files/init", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="upload_init_timeout",
                detail="Upload service initialization timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="upload_init_failed",
                fallback_detail="Upload service initialization failed.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="upload_init_failed",
                detail="Upload service initialization failed.",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise APIError(
                status_code=502,
                code="upload_init_invalid",
                detail="Upload service init response is invalid.",
            ) from exc

        try:
            parsed = UploadInitResponse.model_validate(payload)
        except ValidationError as exc:
            raise APIError(
                status_code=502,
                code="upload_init_invalid",
                detail="Upload service init response is invalid.",
            ) from exc
        return UploadSession(
            upload_id=parsed.upload_id,
            tracking_id=parsed.tracking_id,
        )

    async def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> None:
        if self._stub_upstream:
            logger.info(
                (
                    "Called upload service (stub) action=upload_part "
                    "upload_id=%s part_number=%s bytes=%s"
                ),
                upload_id,
                part_number,
                len(chunk),
            )
            return

        files = {"chunk": ("chunk.bin", chunk, "application/octet-stream")}
        data = {"part_number": str(part_number)}
        try:
            response = await self._client.post(
                f"/uploads/{upload_id}/parts", data=data, files=files
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="upload_part_timeout",
                detail="Upload part timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="upload_part_failed",
                fallback_detail="Upload part failed.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="upload_part_failed",
                detail="Upload part failed.",
            ) from exc

    async def complete_upload(self, upload_id: str, total_bytes: int, total_parts: int) -> None:
        if self._stub_upstream:
            logger.info(
                (
                    "Called upload service (stub) action=complete_upload "
                    "upload_id=%s total_bytes=%s total_parts=%s"
                ),
                upload_id,
                total_bytes,
                total_parts,
            )
            return

        payload = {"total_bytes": total_bytes, "total_parts": total_parts}
        try:
            response = await self._client.post(f"/uploads/{upload_id}/complete", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(
                status_code=504,
                code="upload_complete_timeout",
                detail="Upload completion timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status, code, detail = error_from_downstream_response(
                exc.response,
                fallback_code="upload_complete_failed",
                fallback_detail="Upload completion failed.",
            )
            raise APIError(status_code=status, code=code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise APIError(
                status_code=502,
                code="upload_complete_failed",
                detail="Upload completion failed.",
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()
