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

export async function login(username, password) {
  const result = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  sessionStorage.setItem('medqueue_token', result.access_token);
  sessionStorage.setItem('medqueue_role', result.role || '');
  sessionStorage.setItem('medqueue_user', result.username || username);
  return result;
}
export function logout() {
  sessionStorage.removeItem('medqueue_token');
  sessionStorage.removeItem('medqueue_role');
  sessionStorage.removeItem('medqueue_user');
}
export const getRole = () => sessionStorage.getItem('medqueue_role') || '';
export const getUser = () => sessionStorage.getItem('medqueue_user') || '';
export const getQueue = () => request('/queue');
export const createPatient = (payload) => request('/patients', { method: 'POST', body: JSON.stringify(payload) });
export const createVisit = (payload) => request('/visits', { method: 'POST', body: JSON.stringify(payload) });
export const addVitals = (id, values) => request(`/visits/${id}/vitals`, { method: 'POST', body: JSON.stringify({ values }) });
export const overrideVisit = (id, payload) => request(`/visits/${id}/override`, { method: 'POST', body: JSON.stringify(payload) });
export const setStatus = (id, status) => request(`/visits/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
export const getDoctors = () => request('/doctors');
export const setDoctorStatus = (id, status) => request(`/doctors/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
export const assignDoctor = (visitId, doctorId) => request(`/visits/${visitId}/doctor`, { method: 'PATCH', body: JSON.stringify({ doctor_id: doctorId }) });
export const getAudit = (visitId) => request(`/visits/${visitId}/audit`);
export const extractSymptoms = (visitId, text, language) => request(`/visits/${visitId}/symptoms/extract`, { method: 'POST', body: JSON.stringify({ text, language }) });
export const saveSymptoms = (visitId, symptoms) => request(`/visits/${visitId}/symptoms`, { method: 'POST', body: JSON.stringify({ symptoms }) });
