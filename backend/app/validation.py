"""AFN-022: authentication, streamed byte caps and bounded multipart parsing."""

import hmac
from uuid import UUID

from fastapi import Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Scope, Receive, Send

from app.config import IMAGE_MAX_BYTES
from app.errors import InputError
from app.image_validation import validate_image_bytes
from app.predictor import PredictorInput
from app.schemas import ErrorResponse, PredictFormFields


def error_response(error: InputError, scope: Scope) -> JSONResponse:
    adapter = scope["app"].state.inference_adapter
    return JSONResponse(status_code=error.status, content=ErrorResponse(
        detail=error.detail, error_code=error.code, request_id=error.request_id,
    ).model_dump(mode="json"), headers={
        "X-AFN-Inference-Mode": adapter.mode,
        "X-AFN-Model-State": adapter.state.value, "Cache-Control": "no-store",
    })


class RequestLimitsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/predict":
            await self.app(scope, receive, send)
            return
        config = scope["app"].state.settings
        headers = scope["headers"]
        tokens = [v for k, v in headers if k.lower() == b"x-demo-token"]
        expected = config.demo_token.get_secret_value() if config.demo_token else ""
        if not expected or len(tokens) != 1 or not hmac.compare_digest(tokens[0], expected.encode("utf-8")):
            await error_response(InputError(status=401), scope)(scope, receive, send)
            return
        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        encodings = [v for k, v in headers if k.lower() == b"content-encoding"]
        if (len(lengths) > 1 or (lengths and (not lengths[0].isdigit() or len(lengths[0]) > 20))
                or any(v.lower() != b"identity" for v in encodings)):
            await error_response(InputError(), scope)(scope, receive, send)
            return
        if lengths and int(lengths[0]) > config.max_request_bytes:
            await error_response(InputError(status=413), scope)(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > config.max_request_bytes:
                    raise InputError(status=413)
            return message

        await self.app(scope, limited_receive, send)


class BoundedMultipartParser(MultiPartParser):
    """Extend the pinned Starlette parser's file-size and cleanup behavior.

    Bound file bytes in callbacks before they enter its write queue, and reject
    incomplete forms even if the parser's finalize accepts a missing terminator.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_bytes = 0
        self.complete = False

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self.file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > IMAGE_MAX_BYTES:
                raise InputError(status=413)
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self.complete = True
        super().on_end()

    def close_files(self) -> None:
        # Includes an unfinished part absent from FormData on truncated input.
        # This private list is verified against starlette==1.7.0 and tested for
        # success, parse/decode errors, size limits and client disconnects.
        for file in self._files_to_close_on_error:
            file.close()


async def validate_request(request: Request) -> PredictorInput:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise InputError
    parser = BoundedMultipartParser(request.headers, request.stream(), max_files=1,
                                    max_fields=3, max_part_size=200_000)
    form = None
    request_id = None
    try:
        form = await parser.parse()
        if not parser.complete:
            raise InputError
        ids = form.getlist("request_id")
        if len(ids) == 1 and isinstance(ids[0], str):
            try:
                request_id = UUID(ids[0])
            except ValueError:
                pass
        allowed = {"request_id", "title", "text", "image"}
        if set(form) - allowed or any(len(form.getlist(key)) > 1 for key in allowed):
            raise InputError(request_id)
        fields = PredictFormFields.model_validate({
            "request_id": form.get("request_id"), "title": form.get("title"), "text": form.get("text"),
        })
        image = form.get("image")
        if not isinstance(image, UploadFile):
            raise InputError(request_id)
        image_bytes = await image.read(IMAGE_MAX_BYTES + 1)
        await run_in_threadpool(validate_image_bytes, image_bytes, image.content_type)
        inputs = PredictorInput(**fields.model_dump(), image_bytes=image_bytes)
        request.state.request_id = inputs.request_id
        return inputs
    except InputError as exc:
        if request_id is not None:
            exc.request_id = request_id
        raise
    except (MultiPartException, ValidationError):
        raise InputError(request_id) from None
    finally:
        try:
            if form is not None:
                await form.close()
        finally:
            parser.close_files()
