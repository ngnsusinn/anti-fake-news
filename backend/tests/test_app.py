import json
import anyio
from fastapi import Depends
from fastapi.testclient import TestClient
from conftest import TOKEN, REQUEST_ID, valid_post
from app.config import Settings
from app.main import create_app
from app.predictor import ModelNotReadyError, get_predictor


def make_app(**settings):
    return create_app(Settings(_env_file=None, demo_token=TOKEN, **settings))


def test_lifecycle_without_artifacts_and_cleanup(tmp_path):
    missing = tmp_path / "missing-model"
    app = make_app(model_artifact_path=missing)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.json() == {"service_status": "ok", "model_ready": False,
                                   "contract_version": "0.2.0"}
        assert str(missing) not in response.text and TOKEN not in response.text
        assert app.state.predictor is None
        assert valid_post(client).status_code == 503
    assert app.state.settings is None and app.state.predictor is None
    assert not missing.exists()


def test_auth_rejects_before_receiving_any_body():
    async def run():
        app = make_app()
        sent = []
        async def receive():
            raise AssertionError("Unauthorized requests must not read body")
        async def send(message):
            sent.append(message)
        scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
                     method="POST", scheme="http", path="/predict", root_path="",
                     raw_path=b"/predict", query_string=b"", headers=[],
                     client=("127.0.0.1", 1234), server=("127.0.0.1", 8000))
        async with app.router.lifespan_context(app):
            await app(scope, receive, send)
        assert sent[0]["status"] == 401
        assert json.loads(sent[1]["body"])["request_id"] is None
    anyio.run(run)


def test_di_override_cannot_enable_real_predictions():
    app = make_app()
    sentinel = object()
    @app.get("/probe")
    def probe(provider=Depends(get_predictor)):
        return {"same": provider is sentinel}
    with TestClient(app) as client:
        assert client.get("/probe").status_code == 503
        app.state.predictor = sentinel
        assert client.get("/probe").json() == {"same": True}
        app.dependency_overrides[get_predictor] = lambda: sentinel
        assert valid_post(client).status_code == 503
        assert not client.get("/health").json()["model_ready"]


def test_model_failure_details_are_not_returned():
    app = make_app()
    def unavailable():
        raise ModelNotReadyError("private path secret article")
    app.dependency_overrides[get_predictor] = unavailable
    with TestClient(app) as client:
        response = valid_post(client)
        assert response.status_code == 503
        assert response.json()["request_id"] == REQUEST_ID
        assert "private" not in response.text


def test_openapi_matches_implemented_contract():
    with TestClient(make_app()) as client:
        operation = client.get("/openapi.json").json()["paths"]["/predict"]["post"]
    assert set(operation["responses"]) == {"200", "400", "401", "413", "503"}
    assert operation["requestBody"]["required"] is True
    assert "multipart/form-data" in operation["requestBody"]["content"]
    assert {"name": "X-Demo-Token", "in": "header", "required": True,
            "schema": {"type": "string"}} in operation["parameters"]


def test_app_instances_do_not_share_provider_state():
    first, second = make_app(), make_app()
    with TestClient(first), TestClient(second):
        first.state.predictor = object()
        assert second.state.predictor is None
