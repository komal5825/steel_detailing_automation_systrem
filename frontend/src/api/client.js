import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 800000,
  headers: { 'Content-Type': 'application/json' },
});

const MAX_RETRIES = 2;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shouldRetry(error) {
  const status = error?.response?.status;
  if (!status) return true;
  return [408, 429, 500, 502, 503, 504].includes(status);
}

function normalizeApiError(err) {
  const detail = err.response?.data?.detail;
  const status = err.response?.status ?? null;
  let message = err.message || 'Request failed';
  let rootCause = null;
  let suggestedFix = null;
  let stage = null;

  if (typeof detail === 'string') {
    message = detail;
  } else if (detail?.message) {
    message = detail.message;
    rootCause = detail.root_cause || null;
    suggestedFix = detail.suggested_fix || null;
    stage = detail.stage || null;
  } else if (detail) {
    try {
      message = JSON.stringify(detail);
    } catch {
      message = String(detail);
    }
  }

  const enriched = new Error(message);
  enriched.status = status;
  enriched.detail = detail ?? null;
  enriched.rootCause = rootCause;
  enriched.suggestedFix = suggestedFix;
  enriched.stage = stage;
  enriched.transient = shouldRetry(err);
  return enriched;
}

client.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    if (typeof config.headers?.delete === 'function') {
      config.headers.delete('Content-Type');
    } else if (config.headers) {
      delete config.headers['Content-Type'];
    }
  }
  config.metadata = config.metadata || {};
  config.metadata.retryCount = config.metadata.retryCount || 0;
  return config;
});

client.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    const config = err.config || {};
    const retryCount = config?.metadata?.retryCount || 0;
    if (retryCount < MAX_RETRIES && shouldRetry(err)) {
      config.metadata = config.metadata || {};
      config.metadata.retryCount = retryCount + 1;
      await sleep(300 * Math.pow(2, retryCount));
      return client(config);
    }

    const normalized = normalizeApiError(err);
    console.error('[API Error]', {
      message: normalized.message,
      status: normalized.status,
      stage: normalized.stage,
      rootCause: normalized.rootCause,
      suggestedFix: normalized.suggestedFix,
    });
    return Promise.reject(normalized);
  }
);

export default client;
