"""Run the Chromium extension smoke against local FastAPI dev services."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


ROOT = Path(__file__).resolve().parents[1]


class NoHealthRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_health(endpoint):
    with build_opener(NoHealthRedirects).open(endpoint + "/health", timeout=0.7) as response:
        return response.headers.get("X-AFN-Inference-Mode"), json.load(response)


def loopback_endpoint(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use http://127.0.0.1:<port>") from error
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.path not in ("", "/") or (port is not None and port == 0)):
        raise argparse.ArgumentTypeError("Use http://127.0.0.1:<port>")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("The endpoint cannot contain credentials, a query or a fragment")
    return value.rstrip("/")


@contextmanager
def run_backend(mode, demo_token):
    with socket.socket() as socket_ref:
        socket_ref.bind(("127.0.0.1", 0))
        port = str(socket_ref.getsockname()[1])
    endpoint = "http://127.0.0.1:" + port
    environment = dict(
        os.environ,
        AFN_ENVIRONMENT="test",
        AFN_PREDICTOR_MODE=mode,
        AFN_DEMO_TOKEN=demo_token,
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port],
        cwd=ROOT / "backend",
        env=environment,
    )
    try:
        deadline = time.monotonic() + 10
        while process.poll() is None and time.monotonic() < deadline:
            try:
                observed_mode, health = read_health(endpoint)
            except (OSError, ValueError):
                time.sleep(0.15)
                continue
            if observed_mode != mode or health.get("model_ready") != (mode == "mock"):
                raise RuntimeError("Unexpected FastAPI smoke mode or readiness")
            break
        else:
            raise RuntimeError("FastAPI did not become available")
        yield endpoint
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def run_chromium(environment):
    return subprocess.call(["node", "tests/frontend/browser-smoke.mjs"], cwd=ROOT, env=environment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-endpoint", type=loopback_endpoint, help="Locally running Backend with a locked model")
    args = parser.parse_args()
    environment = os.environ.copy()
    for variable in (
        "AFN_LOCAL_TEST_TOKEN",
        "AFN_MOCK_TEST_URL",
        "AFN_NOT_READY_TEST_URL",
        "AFN_REAL_TEST_URL",
    ):
        environment.pop(variable, None)

    if args.real_endpoint:
        if not environment.get("AFN_REAL_TEST_TOKEN"):
            parser.error("Set AFN_REAL_TEST_TOKEN for the configured real endpoint")
        try:
            mode, health = read_health(args.real_endpoint)
        except (OSError, ValueError):
            parser.error("Could not read health from the configured loopback endpoint")
        if mode != "real" or health.get("model_ready") is not True:
            parser.error("The real endpoint must advertise mode=real and model_ready=true")
        environment["AFN_REAL_TEST_URL"] = args.real_endpoint
        return run_chromium(environment)

    demo_token = token_urlsafe(32)
    with run_backend("mock", demo_token) as mock, run_backend("real", demo_token) as not_ready:
        environment.update(
            AFN_MOCK_TEST_URL=mock,
            AFN_NOT_READY_TEST_URL=not_ready,
            AFN_LOCAL_TEST_TOKEN=demo_token,
        )
        return run_chromium(environment)


if __name__ == "__main__":
    raise SystemExit(main())
