# Anti-fake-news

FastAPI service and Chromium extension for multimodal article analysis.
Python **3.13** is the verified shared setup for Backend and ML on Windows x64.
See [ML environment](docs/ml-environment.md) for shared dependencies and CLIP checks.

## Contents

- [Production](#production) and [development setup](#development-setup)
- [Configuration](#configuration) and [verification](#verification)
- [Contracts and scope](#contracts-and-scope)
- [Final QA report](reports/final-report.md), [acceptance checklist](reports/final-acceptance.md) and [release index](release/release-index.json)

## Production

Follow the [Backend deployment guide](docs/backend-setup.md) to prepare a real
Multimodal bundle and the pinned CLIP cache. Copy `.env.example`
to `.env`, supply `AFN_DEMO_TOKEN` and `AFN_MODEL_METADATA_SHA256`,
then run `python -m app` from `backend/`. The production server starts only after
checking the bundle and warming up the real model. The signed AFN-049 bundle retains
`status: candidate` and requires `AFN_ALLOW_CANDIDATE_MODEL=true`. The
[Chromium extension](docs/extension-setup.md) uses the loopback Backend and the same token.
Set `AFN_EXTENSION_ORIGIN` to the installed extension's origin.

## Development setup

Verified here: Windows x64, Python **3.13.1**. Reuse an existing working virtual environment.
This checkout uses `.venv/issue9`; this implementation creates no additional environment.
Old `.venv`/`.venv/verify` environments refer to an unavailable Python 3.10 installation.
They were preserved, not deleted. A fresh checkout may create one `.venv` with Python 3.13.1
and substitute its interpreter below. Linux/macOS and the complete ML environment are unverified.

From the repository root, PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:AFN_ENVIRONMENT = 'demo'
cd backend
..\.venv\Scripts\python.exe -m app
```

On Linux/macOS (Python 3.13 installed):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
export AFN_ENVIRONMENT=demo
cd backend
../.venv/bin/python -m app
```

No activation needed; stop with Ctrl+C. The launcher honors AFN_HOST/AFN_PORT and accepts
only loopback hosts, default **127.0.0.1:8000**. Settings read root `.env`; process environment
wins. Health and docs: http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.
With the selected interpreter, equivalent explicit command from backend:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Explicit CLI bind options override settings. Keep this local service on loopback.

## Configuration

| Variable | Default / behavior |
| --- | --- |
| AFN_HOST | 127.0.0.1; loopback only |
| AFN_PORT | 8000; 1–65535 |
| AFN_ENVIRONMENT | production in the deployment template; demo mode when unset |
| AFN_PREDICTOR_MODE | real; mock requires dev/test |
| AFN_DEMO_TOKEN | Required for production startup and for authenticated predictions |
| AFN_EXTENSION_ORIGIN | Unset by default. Set to the exact `chrome-extension://<id>` origin for browser CORS grants. |
| AFN_MODEL_ARTIFACT_PATH | Multimodal bundle directory, relative to repo or absolute. The deployment template uses backend/artifacts/multimodal |
| AFN_MODEL_METADATA_SHA256 | SHA-256 of the exact bundle metadata.json, required in production |
| AFN_ALLOW_CANDIDATE_MODEL | False by default. Set to true to deploy a pinned real candidate |
| AFN_MAX_REQUEST_BYTES | Enforced 12 MiB total body default; configurable above 10 MiB |

POST /predict requires X-Demo-Token, UUID, nonblank text (<=50,000 code points), optional
title (<=500), and one JPEG/PNG file (<=10 MiB, <=20 million pixels). Whole-body counting
includes multipart overhead and does not trust Content-Length. Invalid input is 400,
auth failure 401, byte overflow 413, validated input without a model 503. No 422 input errors.
GET /health is unauthenticated and does not imply real inference readiness.

Image validation uses the unchanged shared ML preprocessing helper from PR #68 for EXIF/RGB.
Pillow/NumPy are pinned to that ML manifest. Predictor retains original encoded bytes.
Do not log settings, credentials, articles/images, model exceptions or local artifact paths.

For real mode, install `backend/requirements.txt` and `ml/requirements.txt` into the same
environment, cache the pinned CLIP checkpoint and set `AFN_MODEL_ARTIFACT_PATH` to the
trusted local bundle directory. Startup validates the bundle, loads CLIP offline and warms up
the Predictor. See [bundle setup and lifecycle](docs/model-bundle.md).

## Verification

From the repository root, using the configured Python environment:

```sh
python -m pytest -q tests/test_model_loader.py backend/tests/test_inference_adapter.py
python scripts/test_extension_smoke.py
```

The browser smoke uses temporary loopback servers, an ephemeral token and synthetic inputs.
See [Extension smoke setup](docs/extension-w1.md) for Playwright and Chromium.

## Contracts and scope

- [Backend package and offline setup](docs/backend-setup.md)
- [Data card](docs/data-card.md) and [data rebuild](docs/rebuild-data.md)
- [API contract v0.2.0](docs/api-contract.md)
- [Predictor/shared preprocessing](docs/inference-interface.md)
- [Explicit mock usage and historical AFN-009 evidence](docs/dev-mock.md)
- [AFN-022/023 changes, tests and review handoff](docs/implementation-issues-22-23.md)
- [Historical AFN-007/008 evidence](docs/implementation-issues-7-8.md)
- Project context: [DEFINE.md](DEFINE.md), [DESIGN.md](DESIGN.md), [DIAGRAMS.md](DIAGRAMS.md)

Candidate parity through the deployed Predictor and end-to-end QA remain in
#37–39. See the [week 2 checkpoint](reports/week-2-gate.md) for review status.
