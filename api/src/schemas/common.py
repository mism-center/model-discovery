import secrets
import string
from typing import Annotated

from pydantic import StringConstraints, TypeAdapter

type CustomMetadataValue = str | int | float | bool | None
type CustomMetadata = dict[str, CustomMetadataValue]
MODEL_ID_LENGTH = 12
MODEL_ID_ALPHABET = string.ascii_letters + string.digits
MODEL_ID_PATTERN = r'^[A-Za-z0-9]{12}$'

type ModelId = Annotated[str, StringConstraints(pattern=MODEL_ID_PATTERN)]

_MODEL_ID_ADAPTER = TypeAdapter(ModelId)


def generate_model_id() -> ModelId:
    candidate = ''.join(secrets.choice(MODEL_ID_ALPHABET) for _ in range(MODEL_ID_LENGTH))
    return _MODEL_ID_ADAPTER.validate_python(candidate)
