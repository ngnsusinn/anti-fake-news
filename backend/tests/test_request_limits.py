import json
import anyio
import pytest
from fastapi.testclient import TestClient
from starlette import formparsers
from conftest import AUTH, TOKEN, REQUEST_ID, png_bytes
from app.config import IMAGE_MAX_BYTES, Settings
from app.main import create_app


def app():
    return create_app(Settings(_env_file=None, demo_token=TOKEN,
                               environment="test", predictor_mode="mock"))


def multipart(image=None):
    image = png_bytes() if image is None else image
    return (f'--afn\r\nContent-Disposition: form-data; name="request_id"\r\n\r\n{REQUEST_ID}\r\n'
            '--afn\r\nContent-Disposition: form-data; name="text"\r\n\r\nbody\r\n'
            '--afn\r\nContent-Disposition: form-data; name="image"; filename="test.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + image + b'\r\n--afn--\r\n'


def asgi_post(body, extra_headers=(), chunk_size=65536, disconnect=False):
    async def run():
        service = app()
        messages = []
        offset = 0
        async def receive():
            nonlocal offset
            if disconnect and offset >= len(body):
                return {"type": "http.disconnect"}
            chunk = body[offset:offset + chunk_size]
            offset += len(chunk)
            return {"type": "http.request", "body": chunk,
                    "more_body": disconnect or offset < len(body)}
        async def send(message):
            messages.append(message)
        scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
                     method="POST", scheme="http", path="/predict", root_path="",
                     raw_path=b"/predict", query_string=b"",
                     headers=[(b"x-demo-token", TOKEN.encode()),
                              (b"content-type", b"multipart/form-data; boundary=afn"), *extra_headers],
                     client=("127.0.0.1", 1234), server=("127.0.0.1", 8000))
        async with service.router.lifespan_context(service):
            await service(scope, receive, send)
        return messages[0]["status"], json.loads(messages[1]["body"]), offset
    return anyio.run(run)


@pytest.mark.parametrize("headers", [{}, {"X-Demo-Token": "wrong"},
                                     [("X-Demo-Token", TOKEN), ("X-Demo-Token", TOKEN)]])
def test_auth_before_bad_multipart(headers):
    with TestClient(app()) as client:
        response = client.post("/predict", headers=headers, content=b"invalid")
        assert response.status_code == 401
        assert response.json()["request_id"] is None
        assert TOKEN not in response.text


def test_unconfigured_token_is_fail_closed_in_mock():
    service = create_app(Settings(_env_file=None, environment="test", predictor_mode="mock"))
    with TestClient(service) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/predict", headers=AUTH).status_code == 401


@pytest.mark.parametrize("missing", ["request_id", "text", "image"])
def test_missing_required_part_is_400(missing):
    parts = {"request_id": (None, REQUEST_ID), "text": (None, "body"),
             "image": ("test.png", png_bytes(), "image/png")}
    del parts[missing]
    with TestClient(app()) as client:
        response = client.post("/predict", headers=AUTH, files=parts)
        assert response.status_code == 400


def test_full_10_mib_image_plus_max_text_and_overhead_is_accepted():
    image = png_bytes()
    image += b"\0" * (IMAGE_MAX_BYTES - len(image))
    with TestClient(app()) as client:
        response = client.post("/predict", headers=AUTH,
            data={"request_id": REQUEST_ID, "text": "🙂" * 50_000, "title": "t" * 500},
            files={"image": ("test.png", image, "image/png")})
        assert response.status_code == 200


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_actual_stream_limit_without_or_with_false_length(headers):
    # Valid small file plus epilogue isolates total cap from the file cap.
    body = multipart()
    body += b" " * (12 * 1024 * 1024 + 1 - len(body))
    status, error, read = asgi_post(body, headers)
    assert status == 413 and error["error_code"] == "request_too_large"
    assert error["request_id"] is None


def test_declared_oversize_is_rejected_without_body_reads():
    status, _, read = asgi_post(b"unused", [(b"content-length", b"12582913")])
    assert status == 413 and read == 0


def test_total_request_boundary_exactly_and_plus_one():
    # Valid form plus legal multipart epilogue exercises inclusive total cap.
    body = multipart()
    body += b" " * (12 * 1024 * 1024 - len(body))
    assert asgi_post(body)[0] == 200
    assert asgi_post(body + b" ")[0] == 413


def test_stream_file_limit_and_cleanup(monkeypatch):
    files = []
    original = formparsers.SpooledTemporaryFile
    def tracking(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracking)
    status, error, _ = asgi_post(multipart(b"x" * (IMAGE_MAX_BYTES + 1)))
    assert status == 413 and error["request_id"] is None
    assert files and all(file.closed for file in files)


@pytest.mark.parametrize("truncate", [False, True])
def test_decode_or_truncated_multipart_failure_closes_spooled_files(monkeypatch, truncate):
    files = []
    original = formparsers.SpooledTemporaryFile
    def tracking(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracking)
    body = multipart(b"broken image" * 100_000)
    if truncate:
        body = body[:-12]
    assert asgi_post(body)[0] == 400
    assert files and all(file.closed for file in files)


def test_disconnect_closes_spooled_files(monkeypatch):
    from starlette.requests import ClientDisconnect
    files = []
    original = formparsers.SpooledTemporaryFile
    def tracking(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracking)
    with pytest.raises(ClientDisconnect):
        asgi_post(multipart(b"x" * 2_000_000)[:-12], disconnect=True)
    assert files and all(file.closed for file in files)


@pytest.mark.parametrize("headers", [
    [(b"content-length", b"invalid")], [(b"content-length", b"-1")],
    [(b"content-length", b"1"), (b"content-length", b"1")],
    [(b"content-encoding", b"gzip")],
])
def test_invalid_headers_fail_before_read(headers):
    status, error, read = asgi_post(multipart(), headers)
    assert status == 400 and read == 0 and error["request_id"] is None


@pytest.mark.parametrize("mode", ["real", "mock"])
@pytest.mark.parametrize("mime,data", [("image/jpeg", png_bytes()),
                                       ("image/png", b"private-corrupt-image")])
def test_http_image_errors_precede_provider_and_are_sanitized(mode, mime, data):
    from app.predictor import get_predictor
    service = create_app(Settings(_env_file=None, demo_token=TOKEN,
                                 environment="test", predictor_mode=mode))
    def forbidden_provider():
        raise AssertionError("Invalid images must not reach the provider")
    service.dependency_overrides[get_predictor] = forbidden_provider
    with TestClient(service) as client:
        response = client.post("/predict", headers=AUTH,
            data={"request_id": REQUEST_ID, "text": "private-article"},
            files={"image": ("private-file", data, mime)})
    assert response.status_code == 400
    assert response.json()["request_id"] == REQUEST_ID
    assert "private" not in response.text


@pytest.mark.parametrize("overflow", [False, True])
def test_completed_spooled_file_closed_on_success_or_total_overflow(monkeypatch, overflow):
    files = []
    original = formparsers.SpooledTemporaryFile
    def tracking(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracking)
    image = png_bytes() + b"\0" * 2_000_000
    body = multipart(image)
    if overflow:
        body += b" " * (12 * 1024 * 1024 + 1 - len(body))
    assert asgi_post(body)[0] == (413 if overflow else 200)
    assert files and all(file.closed for file in files)


def test_predictor_receives_original_encoded_bytes_and_separate_text():
    from app.dev.mock_predictor import MockPredictor
    from app.predictor import get_predictor
    received = []
    class Spy:
        def predict(self, inputs):
            received.append(inputs)
            return MockPredictor().predict(inputs)
    service = app()
    service.dependency_overrides[get_predictor] = Spy
    raw = png_bytes(mode="RGBA")
    with TestClient(service) as client:
        response = client.post("/predict", headers=AUTH,
            data={"request_id": REQUEST_ID, "title": " title ", "text": " body "},
            files={"image": ("irrelevant.extension", raw, "image/png")})
    assert response.status_code == 200
    assert len(received) == 1 and received[0].image_bytes == raw
    assert received[0].text == "body" and received[0].title == " title "
