"""Local service: real inference disabled; explicit dev/test mock via AFN-009."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import InputError
from app.validation import RequestLimitsMiddleware, error_response, validate_request
from app.inference_adapter import InferenceAdapter, create_adapter, get_inference_adapter
from app.predictor import ModelNotReadyError, Predictor, PredictorInput, get_predictor
from app.schemas import (
    CONTRACT_VERSION, ErrorResponse, HealthResponse, PredictFormFields,
    PredictionResult, PredictResponse,
)


def inference_headers(adapter: InferenceAdapter) -> dict[str, str]:
    return {"X-AFN-Inference-Mode": adapter.mode,
            "X-AFN-Model-State": adapter.state.value, "Cache-Control": "no-store"}


def predict_request_schema() -> dict:
    schema = PredictFormFields.model_json_schema()
    schema["properties"]["image"] = {"type": "string", "format": "binary"}
    schema["required"].append("image")
    return {"parameters": [{"name": "X-Demo-Token", "in": "header", "required": True,
                            "schema": {"type": "string"}}], "requestBody": {
        "required": True,
        "description": "Authenticated, size-bounded JPEG/PNG upload in all modes.",
        "content": {"multipart/form-data": {"schema": schema}},
    }}


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Resolve config at startup; importing this module never loads artifacts.
        app.state.settings = settings if settings is not None else Settings()
        adapter = create_adapter(app.state.settings)
        app.state.inference_adapter = adapter
        app.state.predictor = adapter if adapter.ready else None
        try:
            yield
        finally:
            adapter.close()
            app.state.predictor = None
            app.state.settings = None

    app = FastAPI(title="Anti-fake-news local foundation", version=CONTRACT_VERSION,
                  lifespan=lifespan)
    app.add_middleware(RequestLimitsMiddleware)

    @app.exception_handler(ModelNotReadyError)
    async def model_not_ready(request: Request, exc: ModelNotReadyError) -> JSONResponse:
        error = ErrorResponse(detail="Model is not ready", error_code="model_not_ready",
                              request_id=getattr(request.state, "request_id", None))
        return JSONResponse(status_code=503, content=error.model_dump(mode="json"),
                            headers=inference_headers(request.app.state.inference_adapter))

    @app.exception_handler(InputError)
    async def input_error(request: Request, exc: InputError) -> JSONResponse:
        return error_response(exc, request.scope)

    @app.get("/health", response_model=HealthResponse)
    def health(response: Response,
               adapter: Annotated[InferenceAdapter, Depends(get_inference_adapter)]) -> HealthResponse:
        response.headers.update(inference_headers(adapter))
        return HealthResponse(model_ready=adapter.ready)

    @app.post(
        "/predict",
        response_model=PredictResponse,
        responses={code: {"model": ErrorResponse} for code in (400, 401, 413, 503)},
        openapi_extra=predict_request_schema(),
        summary="Synthetic prediction only in explicit dev/test mock mode",
        description=(
            "All modes require X-Demo-Token and validated multipart JPEG/PNG input. "
            "Real mode without a model returns 503 after validation. Check X-AFN-Inference-Mode "
            "and the dev-mock model_id; mock output is not a model prediction. "
            "See docs/api-contract.md v0.2.0."
        ),
    )
    async def predict(
        request: Request, response: Response,
        inputs: Annotated[PredictorInput, Depends(validate_request)],
        predictor: Annotated[Predictor, Depends(get_predictor)],
        adapter: Annotated[InferenceAdapter, Depends(get_inference_adapter)],
    ) -> PredictResponse:
        config = request.app.state.settings
        if (config.predictor_mode != "mock" or config.environment not in ("dev", "test")
                or adapter.mode != "mock" or not adapter.ready):
            # An override cannot enable real HTTP inference before #37.
            raise ModelNotReadyError
        start = perf_counter()
        try:
            result = PredictionResult.model_validate(
                await run_in_threadpool(predictor.predict, inputs)
            )
        except Exception:
            # Also covers explicitly overridden providers; never retain error text.
            adapter.mark_error()
            raise ModelNotReadyError from None
        elapsed_ms = max(0, int((perf_counter() - start) * 1000))
        response.headers.update(inference_headers(adapter))
        return PredictResponse(**result.model_dump(), request_id=inputs.request_id,
                               processing_time_ms=elapsed_ms)

    return app


app = create_app()
