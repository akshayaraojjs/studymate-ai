import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
export const STORAGE_KEY = 'studymate.auth';

export const api = axios.create({ baseURL: API_BASE });

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.token ? parsed : null;
  } catch {
    return null;
  }
}

export function storeAuth(auth) {
  if (auth?.token) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const isAuthCall = String(error.config?.url || '').includes('/auth/');
    if (status === 401 && !isAuthCall) {
      storeAuth(null);
      window.dispatchEvent(new Event('studymate:logout'));
    }
    return Promise.reject(error);
  },
);

export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item.msg || 'Invalid input').join(', ');
  }
  if (error?.message) return error.message;
  return fallback;
}
