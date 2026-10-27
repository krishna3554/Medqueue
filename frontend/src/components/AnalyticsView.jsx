import { useEffect, useState } from 'react';
import { getAnalytics } from '../api';

export function AnalyticsView() {
  const [data, setData] = useState(null); const [error, setError] = useState('');
  useEffect(() => { let active = true; getAnalytics().then((result) => active && setData(result)).catch((err) => active && setError(err.message)); return () => { active = false; }; }, []);
  if (error) return <section className="feature-page"><p className="form-error" role="alert">{error}</p></section>;
  if (!data) return <section className="feature-page"><p className="loading-state">Loading operational analytics…</p></section>;
  const max = Math.max(...Object.values(data.triage_distribution), 1);
  return <section className="feature-page"><div className="feature-heading"><span className="eyebrow">Admin view</span><h2>Operational analytics</h2><p>Live summary from the existing queue and audit records. Synthetic/demo data only.</p></div><div className="analytics-grid"><article><span>Total visits</span><strong>{data.total_visits}</strong></article><article><span>Waiting now</span><strong>{data.waiting_visits}</strong></article><article><span>Red flags</span><strong>{data.red_flag_visits}</strong></article><article><span>Overrides</span><strong>{data.override_count}</strong></article></div><section className="analytics-card"><h3>Triage distribution</h3>{Object.entries(data.triage_distribution).map(([level, count]) => <div className="bar-row" key={level}><span>Level {level}</span><div><i style={{ width: `${(count / max) * 100}%` }} /></div><b>{count}</b></div>)}</section><p className="analytics-note">Average current wait: <strong>{data.average_wait_min} min</strong>. Source mix: {Object.entries(data.source_distribution).map(([source, count]) => `${source} ${count}`).join(' · ') || 'no visits'}.</p></section>;
}
