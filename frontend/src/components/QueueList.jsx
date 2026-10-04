import { age, expectedReview, expectedSub } from '../queueUtils';

export function QueueList({ visible, selectedId, onSelect, loading, query, setQuery, filter, setFilter }) {
  return (
    <section className="queue-panel">
      <div className="queue-head">
        <div><h2>Priority order</h2><p>Re-ranked as clinical information changes.</p></div>
        <div className="queue-tools">
          <label className="search"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find patient" /></label>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}><option>All patients</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>Level {n}</option>)}</select>
        </div>
      </div>
      <div className="queue-labels"><span>Patient</span><span>Clinical summary</span><span>Why this position</span><span>Expected review</span></div>
      <div className="patient-list">
        {loading ? <p className="empty-state">Loading queue…</p> : visible.length ? visible.map((p, index) => (
          <button className={`patient ${selectedId === p.id ? 'selected' : ''} ${p.triage.red_flag ? 'red-flag' : ''}`} onClick={() => onSelect(p.id)} key={p.id}>
            <span className="rank">{String(index + 1).padStart(2, '0')}</span>
            <span className={`acuity l${p.triage.level}`}>L{p.triage.level}</span>
            <span className="person"><b>{p.patient.name}</b><small>#{p.id} · {age(p.patient.date_of_birth)} years</small></span>
            <span className="complaint">{p.complaint}</span>
            <span className="factors">{p.triage.red_flag && <i>Red flag</i>}{p.triage.factors.join(' · ') || 'Standard triage'}</span>
            <span className={`eta ${p.triage.red_flag ? 'urgent' : ''}`}>{expectedReview(p)}<small>{expectedSub(p)}</small></span>
            <span className="chevron">›</span>
          </button>
        )) : <p className="empty-state">No patients match this filter.</p>}
      </div>
    </section>
  );
}
