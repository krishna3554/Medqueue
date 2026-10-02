const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const token = sessionStorage.getItem('medqueue_token');
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Request failed');
  return response.status === 204 ? null : response.json();
}

export async function login() {
  const result = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username: 'triage', password: 'medqueue-demo' }) });
  sessionStorage.setItem('medqueue_token', result.access_token);
}
export const getQueue = () => request('/queue');
export const createPatient = (payload) => request('/patients', { method: 'POST', body: JSON.stringify(payload) });
export const createVisit = (payload) => request('/visits', { method: 'POST', body: JSON.stringify(payload) });
export const addVitals = (id, values) => request(`/visits/${id}/vitals`, { method: 'POST', body: JSON.stringify({ values }) });
export const overrideVisit = (id, payload) => request(`/visits/${id}/override`, { method: 'POST', body: JSON.stringify(payload) });
export const setStatus = (id, status) => request(`/visits/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
