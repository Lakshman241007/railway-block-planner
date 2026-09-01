/**
 * Central API Client for Railway Block Planner
 * Connects directly to FastAPI backend on http://127.0.0.1:8000
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    config.signal = controller.signal;

    const response = await fetch(url, config);
    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      let errorJson;
      try {
        errorJson = JSON.parse(errorText);
      } catch {
        errorJson = { detail: errorText || response.statusText };
      }
      const error = new Error(errorJson.detail || `HTTP Error ${response.status}`);
      error.status = response.status;
      error.data = errorJson;
      throw error;
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      const timeoutErr = new Error('Request timed out while connecting to Railway Block Planner backend.');
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    throw err;
  }
}

export async function checkBackendHealth() {
  try {
    const data = await apiFetch('/health');
    return { online: true, data };
  } catch (err) {
    return { online: false, error: err.message };
  }
}
