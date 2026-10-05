import { useCallback, useEffect, useState } from 'react';
import { getQueue } from './api';
import { demoQueue } from './demoQueue';

export function useQueue(enabled) {
  const [queue, setQueue] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const refresh = useCallback(async () => {
    if (!sessionStorage.getItem('medqueue_token')) { setQueue([]); setLoading(false); return; }
    try { setQueue(await getQueue()); setError(''); }
    catch (err) {
      setQueue(demoQueue);
      setError(err.message || 'The queue service is unavailable; showing synthetic demo records.');
    }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    if (!enabled) { setLoading(false); return undefined; }
    refresh(); const timer = window.setInterval(refresh, 5000); return () => window.clearInterval(timer);
  }, [refresh, enabled]);
  return { queue, loading, error, refresh };
}
