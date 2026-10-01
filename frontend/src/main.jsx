import { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const patients = [
  {
    token: 'A–041',
    name: 'Anita R.',
    age: 58,
    complaint: 'Chest tightness · breathlessness',
    level: 1,
    wait: 'Now',
    factors: ['SpO₂ 91%', 'pulse 118'],
    flag: true,
  },
  {
    token: 'A–038',
    name: 'Farhan K.',
    age: 31,
    complaint: 'High fever for 3 days',
    level: 2,
    wait: '06 min',
    factors: ['temp 39.4°', 'duration 3d'],
  },
  {
    token: 'A–039',
    name: 'Meera S.',
    age: 42,
    complaint: 'Severe abdominal pain',
    level: 2,
    wait: '12 min',
    factors: ['pain 8/10', 'pulse 106'],
  },
  {
    token: 'A–036',
    name: 'Gaurav P.',
    age: 67,
    complaint: 'Dizziness · BP 178 / 108',
    level: 3,
    wait: '18 min',
    factors: ['age 67', 'BP elevated'],
  },
  {
    token: 'A–040',
    name: 'Kavita J.',
    age: 24,
    complaint: 'Persistent cough',
    level: 4,
    wait: '31 min',
    factors: ['duration 5d'],
  },
  {
    token: 'A–034',
    name: 'Joseph D.',
    age: 50,
    complaint: 'Medication refill',
    level: 5,
    wait: '42 min',
    factors: ['no red flags'],
  },
];

export function App() {
  const [active, setActive] = useState('Queue');
  const [filter, setFilter] = useState('All patients');
  const [query, setQuery] = useState('');
  const [alertOpen, setAlertOpen] = useState(true);
  const [selected, setSelected] = useState(patients[0]);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [note, setNote] = useState('');
  const [toast, setToast] = useState('');
  const visible = useMemo(
    () =>
      patients.filter(
        (p) =>
          (filter === 'All patients' || `Level ${p.level}` === filter) &&
          `${p.name} ${p.token} ${p.complaint}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [filter, query],
  );
  const notify = (message) => {
    setToast(message);
    setTimeout(() => setToast(''), 2800);
  };
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="MedQueue AI home">
          <span className="brand-mark">M</span>
          <span>
            MedQueue<em>AI</em>
          </span>
        </a>
        <p className="site-name">
          Civic General Hospital
          <br />
          <span>OPD · Ground floor</span>
        </p>
        <nav aria-label="Primary navigation">
          {['Queue', 'Intake', 'Patients', 'Analytics'].map((item) => (
            <button
              key={item}
              className={active === item ? 'nav-link active' : 'nav-link'}
              onClick={() => {
                setActive(item);
                if (item !== 'Queue') notify(`${item} view is ready for the next workflow.`);
              }}
            >
              <span>
                {item === 'Queue'
                  ? '◉'
                  : item === 'Intake'
                    ? '＋'
                    : item === 'Patients'
                      ? '◌'
                      : '⌁'}
              </span>
              {item}
            </button>
          ))}
        </nav>
        <section className="sidebar-foot">
          <div className="live-dot"></div>
          <div>
            <strong>Live coordination</strong>
            <small>Updated 12:42:08</small>
          </div>
        </section>
        <button className="profile">
          <span className="avatar">NK</span>
          <span>
            Nisha Kulkarni<small>Triage nurse</small>
          </span>
          <b>⌄</b>
        </button>
      </aside>
      <section className="workspace" id="top">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Today · Tuesday, 30 September</p>
            <h1>Live queue</h1>
          </div>
          <div className="header-actions">
            <button className="round-button" aria-label="Open notifications">
              ⌁<i></i>
            </button>
            <button className="intake-button" onClick={() => notify('New patient intake opened.')}>
              Start intake <span>＋</span>
            </button>
          </div>
        </header>
        {alertOpen && (
          <section className="alert" role="alert">
            <div className="alert-icon">!</div>
            <div>
              <strong>Immediate review requested</strong>
              <p>
                <b>A–041</b> reported chest tightness and breathlessness. SpO₂ is 91%.
              </p>
            </div>
            <button
              onClick={() => {
                setSelected(patients[0]);
                setAlertOpen(false);
              }}
            >
              Review patient
            </button>
            <button
              className="close"
              aria-label="Dismiss alert"
              onClick={() => setAlertOpen(false)}
            >
              ×
            </button>
          </section>
        )}
        <section className="summary-grid" aria-label="Queue summary">
          <article>
            <span className="metric-icon blue">⌛</span>
            <p>Waiting now</p>
            <strong>18</strong>
            <small>3 added in the last hour</small>
          </article>
          <article>
            <span className="metric-icon amber">↗</span>
            <p>Needs review</p>
            <strong>4</strong>
            <small>Two moved up in queue</small>
          </article>
          <article>
            <span className="metric-icon coral">✦</span>
            <p>Red-flag alerts</p>
            <strong>1</strong>
            <small>Immediate nurse attention</small>
          </article>
          <article>
            <span className="metric-icon navy">⌁</span>
            <p>Average wait</p>
            <strong>
              27 <em>min</em>
            </strong>
            <small>4 min below today’s target</small>
          </article>
        </section>
        <section className="queue-panel">
          <div className="queue-head">
            <div>
              <h2>Priority order</h2>
              <p>Re-ranked as clinical information changes.</p>
            </div>
            <div className="queue-tools">
              <label className="search">
                <span>⌕</span>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Find patient or token"
                />
              </label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                aria-label="Filter queue"
              >
                <option>All patients</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n}>Level {n}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="queue-labels">
            <span>Patient</span>
            <span>Clinical summary</span>
            <span>Why this position</span>
            <span>Expected review</span>
          </div>
          <div className="patient-list">
            {visible.map((p, index) => (
              <button
                className={`patient ${selected.token === p.token ? 'selected' : ''} ${p.flag ? 'red-flag' : ''}`}
                onClick={() => setSelected(p)}
                key={p.token}
              >
                <span className="rank">{String(index + 1).padStart(2, '0')}</span>
                <span className={`acuity l${p.level}`}>L{p.level}</span>
                <span className="person">
                  <b>{p.name}</b>
                  <small>
                    {p.token} · {p.age} years
                  </small>
                </span>
                <span className="complaint">{p.complaint}</span>
                <span className="factors">
                  {p.flag && <i>Red flag</i>}
                  {p.factors.join(' · ')}
                </span>
                <span className={`eta ${p.flag ? 'urgent' : ''}`}>
                  {p.wait}
                  <small>{p.flag ? 'Nurse now' : 'estimated'}</small>
                </span>
                <span className="chevron">›</span>
              </button>
            ))}
          </div>
        </section>
      </section>
      <aside className="detail-panel" aria-label="Selected patient">
        <div className="detail-head">
          <span>Patient brief</span>
          <button onClick={() => setSelected(null)} aria-label="Close patient brief">
            ×
          </button>
        </div>
        {selected ? (
          <>
            <div className={`level-banner l${selected.level}`}>
              <span>Urgency level {selected.level}</span>
              <b>
                {selected.flag
                  ? 'Immediate assessment'
                  : selected.level < 3
                    ? 'Priority review'
                    : 'Standard review'}
              </b>
            </div>
            <section className="patient-title">
              <div className="initials">
                {selected.name
                  .split(' ')
                  .map((x) => x[0])
                  .join('')
                  .replace('.', '')}
              </div>
              <div>
                <h2>{selected.name}</h2>
                <p>
                  {selected.token} · {selected.age} years · Registered 12:21
                </p>
              </div>
            </section>
            <section className="detail-section">
              <h3>Reason for position</h3>
              <p className="explain">
                {selected.flag
                  ? 'Rule matched: chest symptoms with low oxygen saturation.'
                  : 'The triage score considers reported symptoms, vital signs, and time already waiting.'}
              </p>
              <div className="factor-list">
                {selected.factors.map((factor, i) => (
                  <div key={factor}>
                    <span>{factor}</span>
                    <b>+{(0.31 - i * 0.07).toFixed(2)}</b>
                  </div>
                ))}
              </div>
            </section>
            <section className="detail-section vitals">
              <h3>Latest vitals</h3>
              <div>
                <p>
                  <span>Oxygen</span>
                  <b className={selected.flag ? 'danger' : ''}>{selected.flag ? '91' : '98'}%</b>
                </p>
                <p>
                  <span>Pulse</span>
                  <b>{selected.flag ? '118' : '84'} bpm</b>
                </p>
                <p>
                  <span>Blood pressure</span>
                  <b>{selected.flag ? '148 / 92' : '122 / 80'}</b>
                </p>
                <p>
                  <span>Temperature</span>
                  <b>37.2° C</b>
                </p>
              </div>
            </section>
            <section className="staff-note">
              <p>Human judgment is final. This is decision support, not a diagnosis.</p>
              <button className="outline-button" onClick={() => setOverrideOpen(true)}>
                Override priority
              </button>
              <button
                className="primary-button"
                onClick={() => notify(`${selected.token} marked as being reviewed.`)}
              >
                Begin review
              </button>
            </section>
          </>
        ) : (
          <p>Select a patient from the queue.</p>
        )}
      </aside>
      {overrideOpen && (
        <div className="modal-backdrop" role="presentation">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              setOverrideOpen(false);
              notify(`Priority override saved for ${selected.token}.`);
            }}
          >
            <button type="button" className="modal-close" onClick={() => setOverrideOpen(false)}>
              ×
            </button>
            <p className="modal-kicker">Clinical override</p>
            <h2>Set a new priority</h2>
            <p>
              Record why the automated position needs to change. This is saved to the audit log.
            </p>
            <label>
              Override reason
              <textarea
                required
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="For example: clinician assessment indicates immediate review"
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={() => setOverrideOpen(false)}>
                Cancel
              </button>
              <button className="primary-button">Save override</button>
            </div>
          </form>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          ✓ {toast}
        </div>
      )}
    </main>
  );
}
createRoot(document.getElementById('root')).render(<App />);
