"""Local settings; request enforcement lives in validation.py."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_MAX_PIXELS = 20_000_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AFN_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    # The supported launcher is restricted to loopback.
    host: Literal["127.0.0.1", "::1", "localhost"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    environment: Literal["demo", "dev", "test"] = "demo"
    predictor_mode: Literal["real", "mock"] = "real"
    demo_token: SecretStr | None = Field(default=None, repr=False)
    extension_origin: str | None = Field(
        default=None, pattern=r"^chrome-extension://[a-p]{32}$"
    )
    model_artifact_path: Path = Field(default=REPO_ROOT / "artifacts" / "model", repr=False)
    max_request_bytes: int = Field(default=12 * 1024 * 1024, gt=IMAGE_MAX_BYTES)

    @model_validator(mode="after")
    def mock_requires_dev_or_test(self) -> "Settings":
        if self.predictor_mode == "mock" and self.environment not in ("dev", "test"):
            raise ValueError("Mock requires AFN_ENVIRONMENT=dev or test")
        return self

    @field_validator("demo_token", "extension_origin", mode="before")
    @classmethod
    def empty_is_unconfigured(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("model_artifact_path")
    @classmethod
    def resolve_artifact_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else REPO_ROOT / value
