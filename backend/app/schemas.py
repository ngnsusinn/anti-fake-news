"""Contract v0.2.0 schemas. Uploaded files are not JSON model fields."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTRACT_VERSION = "0.2.0"
Label = Literal["fake", "real"]
FakeScore = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
ModelIdentifier = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
ErrorCode = Literal[
    "invalid_input", "invalid_token", "forbidden", "request_too_large", "model_not_ready"
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class PredictFormFields(ContractModel):
    """Text parts AFTER multipart parsing; image remains a separate file part."""

    request_id: UUID
    title: str | None = Field(default=None, strict=True, max_length=500)
    text: str = Field(strict=True, min_length=1, max_length=50_000)

    @field_validator("text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        # max_length is checked on the received string, before trim.
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class PredictionResult(ContractModel):
    """ML output without HTTP correlation or Backend wall-clock timing."""

    label: Label
    fake_score: FakeScore
    model_version: ModelIdentifier
    model_id: ModelIdentifier
    text_truncated: bool = Field(strict=True)


class PredictResponse(PredictionResult):
    request_id: UUID
    processing_time_ms: int = Field(strict=True, ge=0)


class ErrorResponse(ContractModel):
    detail: str = Field(strict=True, min_length=1)
    error_code: ErrorCode
    request_id: UUID | None = None


class HealthResponse(ContractModel):
    service_status: Literal["ok"] = "ok"
    model_ready: bool = Field(strict=True)
    contract_version: Literal["0.2.0"] = CONTRACT_VERSION
