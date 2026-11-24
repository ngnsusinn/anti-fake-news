export class ApiError extends Error {
  constructor(kind, { status, code, requestId } = {}) {
    super(kind);
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

function configForRequest(config) {
  let url;
  try { url = new URL(config.endpoint.trim()); } catch { throw new ApiError('config'); }
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.pathname !== '/'
      || url.username || url.password || url.search || url.hash
      || !Number.isInteger(config.timeoutMs) || config.timeoutMs < 1000 || config.timeoutMs > 120_000) {
    throw new ApiError('config');
  }
  return { base: url.origin, timeoutMs: config.timeoutMs };
}

function isPrediction(data) {
  return data && typeof data.request_id === 'string'
    && ['fake', 'real'].includes(data.label)
    && Number.isFinite(data.fake_score) && data.fake_score >= 0 && data.fake_score <= 1
    && typeof data.model_id === 'string' && Boolean(data.model_id.trim())
    && typeof data.model_version === 'string' && Boolean(data.model_version.trim())
    && Number.isInteger(data.processing_time_ms) && data.processing_time_ms >= 0
    && typeof data.text_truncated === 'boolean';
}

export function createApiClient(fetchTransport = globalThis.fetch) {
  async function request(config, path, options = {}, signal) {
    const { base, timeoutMs } = configForRequest(config);
    if (signal?.aborted) throw new ApiError('aborted');
    const controller = new AbortController();
    const abort = () => controller.abort();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; abort(); }, timeoutMs);
    signal?.addEventListener('abort', abort, { once: true });
    try {
      const response = await fetchTransport(base + path, {
        ...options, signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error',
      });
      const raw = await response.text();
      let data;
      try { data = JSON.parse(raw); } catch { /* A failed response might be plain text. */ }
      if (!response.ok) throw new ApiError('http', {
        status: response.status,
        code: typeof data?.error_code === 'string' ? data.error_code : null,
        requestId: typeof data?.request_id === 'string' ? data.request_id : null,
      });
      if (timedOut) throw new ApiError('timeout');
      if (signal?.aborted) throw new ApiError('aborted');
      return { data, mode: response.headers.get('X-AFN-Inference-Mode') };
    } catch (error) {
      if (timedOut) throw new ApiError('timeout');
      if (signal?.aborted) throw new ApiError('aborted');
      if (error instanceof ApiError) throw error;
      throw new ApiError('network');
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }

  return {
    async health(config, signal) {
      const response = await request(config, '/health', {}, signal);
      if (response.data?.service_status !== 'ok' || typeof response.data.model_ready !== 'boolean'
          || typeof response.data.contract_version !== 'string') throw new ApiError('invalid-response');
      return response;
    },

    async predict(config, draft, requestId, signal) {
      const body = new FormData();
      body.set('request_id', requestId);
      body.set('title', draft.title);
      body.set('text', draft.text);
      body.set('image', draft.image);
      const response = await request(config, '/predict', {
        method: 'POST', headers: { 'X-Demo-Token': config.demoToken.trim() }, body,
      }, signal);
      if (!isPrediction(response.data)) throw new ApiError('invalid-response');
      return response;
    },
  };
}
