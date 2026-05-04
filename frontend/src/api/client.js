import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    if (typeof config.headers?.delete === 'function') {
      config.headers.delete('Content-Type');
    } else if (config.headers) {
      delete config.headers['Content-Type'];
    }
  }
  return config;
});

client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Request failed';
    console.error('[API Error]', msg);
    return Promise.reject(new Error(msg));
  }
);

export default client;
