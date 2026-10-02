import { useCallback, useEffect, useState } from 'react';
import { getQueue, login } from './api';
import { demoQueue } from './demoQueue';

export function useQueue() {
  const [queue, setQueue] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const refresh = useCallback(async () => {
    try { if (!sessionStorage.getItem('medqueue_token')) await login(); setQueue(await getQueue()); setError(''); }
    catch (err) {
      setQueue(demoQueue);
      setError(err.message || 'The queue service is unavailable; showing synthetic demo records.');
    }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 5000); return () => window.clearInterval(timer); }, [refresh]);
  return { queue, loading, error, refresh };
}
