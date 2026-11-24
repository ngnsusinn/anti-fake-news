import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import AUTH, TOKEN, png_bytes

from app.config import IMAGE_MAX_BYTES, Settings
from app.dev.mock_predictor import MOCK_MODEL_ID
from app.inference_adapter import InferenceAdapter, ModelState, get_inference_adapter
from app.main import create_app
from app.predictor import get_predictor
from app.schemas import CONTRACT_VERSION, ErrorResponse, HealthResponse, PredictResponse

FIXTURES = Path(__file__).parent / "fixtures" / "api" / "v0.2.0"
REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def mock_app():
    return create_app(Settings(_env_file=None, demo_token=TOKEN, environment="test", predictor_mode="mock"))


def post_mock(client, **overrides):
    data = {"request_id": REQUEST_ID, "title": "Synthetic title", "text": "Synthetic article"}
    data.update(overrides)
    return client.post("/predict", data=data,
                       files={"image": ("mock.png", png_bytes(), "image/png")})


def test_mock_http_matches_versioned_fixtures_and_echoes_uuid(mock_app):
    with TestClient(mock_app, headers=AUTH) as client:
        health = client.get("/health")
        assert health.json() == fixture("health-mock-ready.json")
        assert health.headers["X-AFN-Inference-Mode"] == "mock"
        assert health.headers["X-AFN-Model-State"] == "ready"
        response = post_mock(client)
        assert response.status_code == 200
        actual = PredictResponse.model_validate(response.json())
        expected = fixture("predict-mock.json")
        # Wall-clock time is measured, not fixed fixture performance evidence.
        expected["processing_time_ms"] = actual.processing_time_ms
        assert response.json() == expected
        assert actual.request_id == UUID(REQUEST_ID)
        assert actual.model_id == MOCK_MODEL_ID
        assert response.headers["X-AFN-Inference-Mode"] == "mock"
        assert response.headers["Cache-Control"] == "no-store"
    assert mock_app.state.inference_adapter.state == ModelState.NOT_LOADED


@pytest.mark.parametrize("field,value,correlated", [
    ("request_id", "bad", False), ("request_id", "", False),
    ("text", " \n ", True), ("text", "a" * 50_001, True),
    ("title", "a" * 501, True),
], ids=["malformed-uuid", "empty-uuid", "blank-text", "long-text", "long-title"])
def test_invalid_mock_fields_are_sanitized_400(mock_app, field, value, correlated):
    with TestClient(mock_app, headers=AUTH) as client:
        response = post_mock(client, **{field: value})
        assert response.status_code == 400
        expected = fixture("invalid-input-correlated.json" if correlated else "invalid-input.json")
        assert response.json() == expected
        assert client.get("/health").json()["model_ready"] is True


def test_missing_image_json_and_malformed_multipart_are_400(mock_app):
    with TestClient(mock_app, headers=AUTH) as client:
        responses = [
            client.post("/predict", json={"request_id": REQUEST_ID}),
            client.post("/predict", content=b"malformed", headers={"Content-Type": "multipart/form-data"}),
            client.post("/predict", files={"request_id": (None, REQUEST_ID), "text": (None, "body")}),
            client.post("/predict", files={"request_id": (None, REQUEST_ID), "text": (None, "body"),
                                           "image": ("empty.png", b"", "image/png")}),
        ]
        assert [response.status_code for response in responses] == [400] * 4
        assert all(response.json()["error_code"] == "invalid_input" for response in responses)


def test_duplicate_uuid_is_ambiguous_and_not_echoed(mock_app):
    with TestClient(mock_app, headers=AUTH) as client:
        response = client.post("/predict", files=[
            ("request_id", (None, REQUEST_ID)), ("request_id", (None, REQUEST_ID)),
            ("text", (None, "body")), ("image", ("mock.png", b"mock")),
        ])
        assert response.status_code == 400
        assert response.json() == fixture("invalid-input.json")


def test_streaming_image_byte_guard(mock_app):
    with TestClient(mock_app, headers=AUTH) as client:
        response = client.post("/predict", data={"request_id": REQUEST_ID, "text": "body"},
                               files={"image": ("mock.png", b"x" * (IMAGE_MAX_BYTES + 1))})
        assert response.status_code == 413
        assert response.json() == fixture("request-too-large.json")


def test_mock_failure_changes_health_to_error_without_leaking_details(mock_app):
    class FailingPredictor:
        def predict(self, inputs):
            raise RuntimeError("private token /private/model/path " + inputs.text)

    with TestClient(mock_app, headers=AUTH) as client:
        mock_app.dependency_overrides[get_predictor] = FailingPredictor
        response = post_mock(client)
        assert response.status_code == 503
        assert response.json() == fixture("not-ready-correlated.json")
        assert response.headers["X-AFN-Model-State"] == "error"
        health = client.get("/health")
        assert health.json()["model_ready"] is False
        assert health.headers["X-AFN-Model-State"] == "error"
        assert "private" not in response.text + health.text
        mock_app.dependency_overrides.clear()
        assert post_mock(client).status_code == 503  # No implicit recovery/fallback.


def test_health_uses_adapter_dependency_and_does_not_expose_settings():
    app = create_app(Settings(_env_file=None, demo_token="private-test-only"))
    adapter = InferenceAdapter()
    adapter.mark_error()
    app.dependency_overrides[get_inference_adapter] = lambda: adapter
    with TestClient(app, headers=AUTH) as client:
        response = client.get("/health")
        assert response.json() == fixture("health-real-not-loaded.json")
        assert response.headers["X-AFN-Model-State"] == "error"
        assert "private-test-only" not in response.text


def test_default_real_http_matches_fixture_and_does_not_fallback():
    app = create_app(Settings(_env_file=None, demo_token=TOKEN))
    with TestClient(app, headers=AUTH) as client:
        assert client.get("/health").json() == fixture("health-real-not-loaded.json")
        response = post_mock(client)
        assert response.status_code == 503
        assert response.json() == fixture("not-ready-correlated.json")
        assert response.headers["X-AFN-Inference-Mode"] == "real"
        assert response.headers["X-AFN-Model-State"] == "not_loaded"


def test_fixture_manifest_and_bodies_agree_with_schemas():
    manifest = fixture("manifest.json")
    assert manifest["contract_version"] == CONTRACT_VERSION
    schemas = {"HealthResponse": HealthResponse, "PredictResponse": PredictResponse,
               "ErrorResponse": ErrorResponse}
    for case in manifest["cases"]:
        schemas[case["schema"]].model_validate(fixture(case["body_file"]))


def test_mock_timing_measures_call_without_model_loading(mock_app, monkeypatch):
    from app import main

    clock = iter([10.0, 10.125])
    monkeypatch.setattr(main, "perf_counter", lambda: next(clock))
    with TestClient(mock_app, headers=AUTH) as client:
        assert post_mock(client).json()["processing_time_ms"] == 125


def test_mock_provider_is_recreated_on_each_lifespan(mock_app):
    with TestClient(mock_app, headers=AUTH) as client:
        old = mock_app.state.inference_adapter
        old.mark_error()
        assert client.get("/health").json()["model_ready"] is False
    with TestClient(mock_app, headers=AUTH) as client:
        assert mock_app.state.inference_adapter is not old
        assert client.get("/health").json()["model_ready"] is True


def test_failed_mock_startup_serves_error_health_without_fallback(monkeypatch):
    from app.dev import mock_predictor

    def fail():
        raise RuntimeError("private-startup-path test-only-secret")

    monkeypatch.setattr(mock_predictor, "MockPredictor", fail)
    app = create_app(Settings(_env_file=None, demo_token=TOKEN, environment="test", predictor_mode="mock"))
    with TestClient(app, headers=AUTH) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_ready"] is False
        assert health.headers["X-AFN-Inference-Mode"] == "mock"
        assert health.headers["X-AFN-Model-State"] == "error"
        response = post_mock(client)
        assert response.status_code == 503
        assert response.json() == fixture("not-ready-correlated.json")
        assert "private" not in health.text + response.text
        assert app.state.predictor is None
