# API fixtures v0.2.0

Synthetic response examples, not real ML predictions or measured performance.
manifest.json records HTTP status and headers; all bodies validate against current schemas.
Inputs now require X-Demo-Token and a valid JPEG/PNG in every mode. Real mode 503 echoes
validated UUID; early auth/parser/byte-limit errors can have null UUID. not-ready.json
retains the nullable schema example, not the normal validated real HTTP response.
Mock model_version remains mock-v0.1.1 because the synthetic provider is unchanged.
Fixture processing_time_ms=0 is a placeholder. v0.1.1 fixtures remain untouched as history.
ML/Extension consumer review is pending.
