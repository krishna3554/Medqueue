import { useCallback, useEffect, useRef, useState } from 'react';
import { getQueue } from './api';
import { demoQueue } from './demoQueue';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const wsUrl = () => `${API_URL.replace(/^http/, 'ws')}/ws/queue?token=${sessionStorage.getItem('medqueue_token') || ''}`;

export function useQueue(enabled) {
  const [queue, setQueue] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [live, setLive] = useState(false); const [alert, setAlert] = useState(null);
  const pollRef = useRef(null);
  const refresh = useCallback(async () => {
    if (!sessionStorage.getItem('medqueue_token')) { setQueue([]); setLoading(false); return; }
    try { setQueue(await getQueue()); setError(''); }
    catch (err) {
      setQueue(demoQueue);
      setError(err.message || 'The queue service is unavailable; showing synthetic demo records.');
    }
    finally { setLoading(false); }
  }, []);
  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    refresh();
    pollRef.current = window.setInterval(refresh, 5000);
  }, [refresh]);
  const stopPolling = useCallback(() => {
    if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
  }, []);
  useEffect(() => {
    if (!enabled) { setLoading(false); return undefined; }
    if (typeof WebSocket === 'undefined') { startPolling(); return () => stopPolling(); }
    let socket = null;
    let closed = false;
    try {
      socket = new WebSocket(wsUrl());
    } catch {
      startPolling();
      return () => stopPolling();
    }
    socket.onopen = () => { setLive(true); stopPolling(); };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'queue') { setQueue(message.data); setError(''); setLoading(false); }
        if (message.type === 'red_flag_alert') setAlert({ ids: message.ids, count: message.count, at: Date.now() });
      } catch { /* keep polling fallback */ }
    };
    socket.onerror = () => { setLive(false); startPolling(); };
    socket.onclose = () => { if (!closed) { setLive(false); startPolling(); } };
    const fallback = window.setTimeout(() => { if (!closed && socket.readyState !== 1) startPolling(); }, 3000);
    refresh();
    return () => { closed = true; window.clearTimeout(fallback); try { socket.close(); } catch { /* noop */ } stopPolling(); };
  }, [refresh, enabled, startPolling, stopPolling]);
  return { queue, loading, error, refresh, live, alert };
}
