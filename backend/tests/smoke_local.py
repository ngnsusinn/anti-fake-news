"""Optional real-socket smoke: run from backend with `python tests/smoke_local.py`.

Uses the documented Uvicorn command and always stops the child it starts.
Generates an ephemeral token and synthetic PNG; no model or user data is needed.
"""

import argparse
import json
import os
import secrets
from io import BytesIO
from PIL import Image
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("real", "mock"), default="real")
    mode = parser.parse_args().mode
    # Refuse to test against or stop an unrelated server already using this port.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 8000))

    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
               "127.0.0.1", "--port", "8000", "--no-access-log"]
    environment = os.environ.copy()
    token = secrets.token_urlsafe(32)
    environment.update(AFN_ENVIRONMENT="test" if mode == "mock" else "demo",
                       AFN_PREDICTOR_MODE=mode, AFN_DEMO_TOKEN=token,
                       AFN_MAX_REQUEST_BYTES=str(12 * 1024 * 1024))
    process = subprocess.Popen(
        command, cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    opener = build_opener(ProxyHandler({}))
    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError("Uvicorn exited before startup")
            try:
                with opener.open("http://127.0.0.1:8000/health", timeout=1) as response:
                    assert response.status == 200
                    assert json.load(response) == {
                        "service_status": "ok", "model_ready": mode == "mock",
                        "contract_version": "0.2.0",
                    }
                    assert response.headers["X-AFN-Inference-Mode"] == mode
                break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Uvicorn startup timed out") from None
                time.sleep(0.1)
        print(f"GET /health: 200; mode={mode}; model_ready={mode == 'mock'}")
        request_id = "550e8400-e29b-41d4-a716-446655440000"
        boundary = "afn-smoke-boundary"
        with BytesIO() as buffer, Image.new("RGB", (2, 2)) as image:
            image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
        payload = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="request_id"\r\n\r\n'
                f'{request_id}\r\n--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\n'
                f'Synthetic smoke article\r\n--{boundary}\r\n'
                'Content-Disposition: form-data; name="image"; filename="mock.png"\r\n'
                'Content-Type: image/png\r\n\r\n'
            ).encode() + image_bytes + f'\r\n--{boundary}--\r\n'.encode()
        request = Request("http://127.0.0.1:8000/predict", data=payload, method="POST",
                          headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                   "X-Demo-Token": token})
        try:
            opener.open(Request("http://127.0.0.1:8000/predict", method="POST"), timeout=2)
        except HTTPError as response:
            with response:
                assert response.code == 401
                assert json.load(response)["error_code"] == "invalid_token"
        else:
            raise AssertionError("Missing token must be rejected")
        print("POST /predict without token: 401")
        if mode == "mock":
            with opener.open(request, timeout=2) as response:
                result = json.load(response)
                assert response.status == 200
                assert response.headers["X-AFN-Inference-Mode"] == "mock"
                assert result["model_id"] == "dev-mock-not-a-model"
                assert result["request_id"] == request_id
                assert result["processing_time_ms"] >= 0
            print("POST /predict: 200; dev-mock-not-a-model; synthetic output only")
            return
        try:
            opener.open(request, timeout=2)
        except HTTPError as response:
            with response:
                assert response.code == 503
                assert json.load(response) == {
                    "detail": "Model is not ready", "error_code": "model_not_ready",
                    "request_id": request_id,
                }
        else:
            raise AssertionError("Prediction must not succeed")
        print("POST /predict: 503; model_not_ready; validated request_id echoed")
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)
        # No access logs; never print the generated token or request body.
        print(output.strip())
        print("Stopped smoke server process:", process.poll() is not None)


if __name__ == "__main__":
    main()
