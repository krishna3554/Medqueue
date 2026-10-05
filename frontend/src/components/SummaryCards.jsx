export function SummaryCards({ queue, avg, error }) {
  return (
    <section className="summary-grid">
      <article><span className="metric-icon blue">⌛</span><p>Waiting now</p><strong>{queue.length}</strong><small>{error ? 'Synthetic demo data' : 'Live API data'}</small></article>
      <article><span className="metric-icon amber">↗</span><p>Needs review</p><strong>{queue.filter((p) => p.triage.level <= 2).length}</strong><small>Level 1–2 patients</small></article>
      <article><span className="metric-icon coral">✦</span><p>Red-flag alerts</p><strong>{queue.filter((p) => p.triage.red_flag).length}</strong><small>Immediate nurse attention</small></article>
      <article><span className="metric-icon navy">⌁</span><p>Average wait</p><strong>{avg} <em>min</em></strong><small>From registration times</small></article>
    </section>
  );
}
