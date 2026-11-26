"""Exercise the Backend over loopback with a synthetic input and an ephemeral token.

Run from backend with python tests/smoke_local.py. Use --bundle and
--metadata-sha256 to verify an AFN-049 frozen, non-fixture multimodal bundle.
Use --bundle and --candidate to smoke-test a real candidate in demo mode.
"""

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from PIL import Image


def read_bundle_metadata(bundle: Path, expected_hash: str | None, expected_status: str) -> dict:
    content = (bundle / "metadata.json").read_bytes()
    if expected_hash and hashlib.sha256(content).hexdigest() != expected_hash.lower():
        raise ValueError("Bundle metadata SHA-256 differs from the supplied value")
    metadata = json.loads(content)
    if (not isinstance(metadata, dict)
            or metadata.get("schema_version") != "afn-model-bundle-v1"
            or metadata.get("status") != expected_status
            or metadata.get("configuration") != "multimodal"
            or metadata.get("is_fixture") is not False
            or any(not isinstance(metadata.get(key), str) or not metadata[key].strip()
                   for key in ("model_id", "model_version"))):
        raise ValueError(f"Expected a non-fixture multimodal bundle with status {expected_status}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("real", "mock"), default="real")
    parser.add_argument("--bundle", type=Path, help="Path to a real multimodal bundle")
    parser.add_argument("--candidate", action="store_true", help="Run a real candidate in demo mode")
    parser.add_argument("--metadata-sha256", help="Independent metadata.json digest from AFN-049")
    args = parser.parse_args()
    if (args.candidate or args.metadata_sha256) and not args.bundle:
        parser.error("--candidate and --metadata-sha256 require --bundle")
    if args.bundle and args.mode != "real":
        parser.error("--bundle requires real mode")
    if args.bundle and not (args.candidate or args.metadata_sha256):
        parser.error("A frozen bundle requires --metadata-sha256 from AFN-049")
    metadata = None
    if args.bundle:
        try:
            expected_status = "candidate" if args.candidate else "frozen"
            metadata = read_bundle_metadata(args.bundle, args.metadata_sha256, expected_status)
        except (OSError, ValueError) as error:
            parser.exit(1, f"Bundle preflight failed: {error}\n")

    # Reserve an available port to avoid contacting or stopping an unrelated service.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    expect_ready = args.mode == "mock" or metadata is not None
    command = [sys.executable, "-m", "app"]
    environment = os.environ.copy()
    token = secrets.token_urlsafe(32)
    runtime = "test" if args.mode == "mock" else "demo"
    if metadata and not args.candidate:
        runtime = "production"
    environment.update(
        AFN_HOST="127.0.0.1",
        AFN_PORT=str(port),
        AFN_ENVIRONMENT=runtime,
        AFN_PREDICTOR_MODE=args.mode,
        AFN_DEMO_TOKEN=token,
        AFN_MODEL_METADATA_SHA256=args.metadata_sha256 or "",
        AFN_MAX_REQUEST_BYTES=str(12 * 1024 * 1024),
        HF_HUB_OFFLINE="1",
    )
    process_options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}

    with TemporaryDirectory(prefix="afn-smoke-") as temporary:
        bundle = args.bundle.resolve() if args.bundle else Path(temporary) / "absent-model"
        environment["AFN_MODEL_ARTIFACT_PATH"] = str(bundle)
        print(f"Backend smoke environment: {runtime}")
        process = subprocess.Popen(
            command, cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=environment, **process_options,
        )
        try:
            exercise_service(process, base_url, args.mode, expect_ready, token, metadata)
        finally:
            process.terminate()
            try:
                output, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate(timeout=5)
            print(output.strip())
            print("Stopped smoke server process:", process.poll() is not None)


def exercise_service(process, base_url, mode, expect_ready, token, metadata) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + (120 if metadata else 15)
    while True:
        if process.poll() is not None:
            raise RuntimeError("Backend exited before startup")
        try:
            with opener.open(base_url + "/health", timeout=1) as response:
                assert response.status == 200
                assert json.load(response) == {
                    "service_status": "ok", "model_ready": expect_ready, "contract_version": "0.2.0",
                }
                assert response.headers["X-AFN-Inference-Mode"] == mode
                if expect_ready:
                    assert response.headers["X-AFN-Model-State"] == "ready"
            break
        except (URLError, TimeoutError):
            if time.monotonic() >= deadline:
                raise RuntimeError("Backend startup timed out") from None
            time.sleep(0.1)
    print(f"GET /health: 200; mode={mode}; model_ready={expect_ready}")

    predict_url = base_url + "/predict"
    try:
        opener.open(Request(predict_url, method="POST"), timeout=2)
    except HTTPError as response:
        with response:
            assert response.code == 401
            assert json.load(response)["error_code"] == "invalid_token"
    else:
        raise AssertionError("Missing token must be rejected")
    print("POST /predict without token: 401")

    request_id = "550e8400-e29b-41d4-a716-446655440000"
    boundary = "afn-smoke-boundary"
    with BytesIO() as buffer, Image.new("RGB", (32, 32), (80, 120, 180)) as image:
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
    payload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="request_id"\r\n\r\n'
        f'{request_id}\r\n--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\n'
        f'Synthetic smoke article\r\n--{boundary}\r\n'
        'Content-Disposition: form-data; name="image"; filename="smoke.png"\r\n'
        'Content-Type: image/png\r\n\r\n'
    ).encode() + image_bytes + f'\r\n--{boundary}--\r\n'.encode()
    request = Request(predict_url, data=payload, method="POST", headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}", "X-Demo-Token": token,
    })
    if expect_ready:
        with opener.open(request, timeout=30) as response:
            result = json.load(response)
            assert response.status == 200
            assert response.headers["X-AFN-Inference-Mode"] == mode
            assert result["model_id"] == (metadata["model_id"] if metadata else "dev-mock-not-a-model")
            if metadata:
                assert result["model_version"] == metadata["model_version"]
            assert result["request_id"] == request_id
            assert result["label"] in ("fake", "real")
            assert 0 <= result["fake_score"] <= 1
            assert result["processing_time_ms"] >= 0
            assert result["text_truncated"] is False
        print(f"POST /predict: 200; {result['model_id']} {result['model_version']}; synthetic input")
        return

    try:
        opener.open(request, timeout=2)
    except HTTPError as response:
        with response:
            assert response.code == 503
            assert json.load(response) == {
                "detail": "Model is not ready", "error_code": "model_not_ready", "request_id": request_id,
            }
    else:
        raise AssertionError("Prediction must not succeed")
    print("POST /predict: 503; model_not_ready; validated request_id echoed")


if __name__ == "__main__":
    main()
