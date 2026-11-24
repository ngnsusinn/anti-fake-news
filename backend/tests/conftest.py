import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Never let developer AFN settings change deterministic tests."""
    for name in os.environ:
        if name.upper().startswith("AFN_"):
            monkeypatch.delenv(name)


from io import BytesIO
from PIL import Image

TOKEN = "test-only-auth-token"
AUTH = {"X-Demo-Token": TOKEN}
REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"


def png_bytes(size=(2, 2), mode="RGB", **save_kwargs):
    with Image.new(mode, size) as image, BytesIO() as stream:
        image.save(stream, format="PNG", **save_kwargs)
        return stream.getvalue()


def valid_post(client):
    return client.post("/predict", headers=AUTH,
                       data={"request_id": REQUEST_ID, "text": "Synthetic article"},
                       files={"image": ("test.png", png_bytes(), "image/png")})
