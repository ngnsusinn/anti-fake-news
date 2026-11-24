"""Sanitized contract failures, shared by transport and image validation."""

from uuid import UUID

from app.schemas import ErrorCode


class InputError(Exception):
    def __init__(self, request_id: UUID | None = None, *, status: int = 400) -> None:
        self.request_id = request_id
        self.status = status
        self.code: ErrorCode = {400: "invalid_input", 401: "invalid_token",
                                413: "request_too_large"}[status]
        self.detail = {400: "Invalid input", 401: "Invalid token",
                       413: "Request is too large"}[status]
