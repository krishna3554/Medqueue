import { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  addVitals,
  assignDoctor,
  createPatient,
  createVisit,
  extractSymptoms,
  getAudit,
  getDoctors,
  getRole,
  getUser,
  login,
  logout,
  overrideVisit,
  saveSymptoms,
  setDoctorStatus,
  setStatus,
} from './api';
import { useQueue } from './useQueue';
import './styles.css';

const symptoms = ['chest_pain', 'chest_tightness', 'breathlessness', 'fever', 'dizziness', 'abdominal_pain', 'cough'];
const age = (dob) => (dob ? new Date().getFullYear() - new Date(dob).getFullYear() : '—');
const waitedMin = (p) => Math.max(0, Math.round((Date.now() - new Date(p.registered_at)) / 60000));
const expectedReview = (p) => {
  if (p.est_wait_min === null || p.est_wait_min === undefined) return p.triage.red_flag ? 'Now' : `${waitedMin(p)} min`;
  if (p.triage.red_flag && p.est_wait_min === 0) return 'Now';
  return `~${p.est_wait_min} min`;
};
const expectedSub = (p) => {
  if (p.est_wait_min === null || p.est_wait_min === undefined) return p.triage.red_flag ? 'Nurse now' : 'waiting';
  if (p.triage.red_flag && p.est_wait_min === 0) return 'Nurse now';
  return 'estimated';
};

// eslint-disable-next-line no-unused-vars
function Login({ onLogin }) {
  const [form, setForm] = useState({ username: 'nurse', password: 'medqueue-demo' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const result = await login(form.username, form.password);
      onLogin(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top"><span className="brand-mark">M</span><span>MedQueue<em>AI</em></span></a>
        <p className="site-name">Civic General Hospital<br /><span>OPD · Ground floor</span></p>
      </aside>
      <section className="workspace" id="top">
        <header className="topbar"><div><p className="breadcrumb">Decision support · pending clinical review</p><h1>Sign in</h1></div></header>
        <section className="queue-panel intake-form">
          <div className="queue-head"><div><h2>Clinical sign in</h2><p>Dev users: registration · nurse · clinician · admin (password medqueue-demo).</p></div></div>
          <form onSubmit={submit}>
            <label>Username<input required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></label>
            <label>Password<input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
            {error && <p className="form-error">{error}</p>}
            <button className="primary-button wide" disabled={saving}>{saving ? 'Signing in…' : 'Sign in'}</button>
          </form>
        </section>
      </section>
    </main>
  );
}

// eslint-disable-next-line no-unused-vars
function Intake({ complete }) {
  const [form, setForm] = useState({ name: '', date_of_birth: '', complaint: '', freeText: '', lang: 'hi', symptoms: [], spo2: '', pulse: '', sbp: '', temp_c: '' });
  const [error, setError] = useState(''); const [saving, setSaving] = useState(false);
  const [stage, setStage] = useState('form'); const [visitId, setVisitId] = useState(null);
  const [candidates, setCandidates] = useState([]); const [confirmed, setConfirmed] = useState([]);
  const [listening, setListening] = useState(false); const [speechError, setSpeechError] = useState('');
  const update = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const speechSupported = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const langTag = form.lang === 'hi' ? 'hi-IN' : form.lang === 'mr' ? 'mr-IN' : 'en-IN';
  const startVoice = () => {
    setSpeechError('');
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) { setSpeechError('Voice input is not supported in this browser. Use the picklist below.'); return; }
    try {
      const rec = new Ctor(); rec.lang = langTag; rec.interimResults = false;
      rec.onresult = (e) => { const text = e.results[0][0].transcript; update('freeText', form.freeText ? `${form.freeText} ${text}` : text); };
      rec.onerror = () => setSpeechError('Microphone was denied or unavailable. Use the picklist below.');
      rec.onend = () => setListening(false);
      setListening(true); rec.start();
    } catch { setSpeechError('Microphone was denied or unavailable. Use the picklist below.'); setListening(false); }
  };
  const register = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const patient = await createPatient({ name: form.name, date_of_birth: form.date_of_birth || null });
      const visit = await createVisit({ patient_id: patient.id, complaint: form.complaint, symptoms: [] });
      setVisitId(visit.id);
      let extracted = [];
      if (form.freeText.trim()) {
        try { const res = await extractSymptoms(visit.id, form.freeText, form.lang); extracted = res.candidates || []; }
        catch (err) { setError(`Extraction failed (${err.message}); confirm from the picklist.`); }
      }
      const suggested = extracted.filter((c) => !c.negated).map((c) => c.canonical);
      const merged = [...new Set([...suggested, ...form.symptoms])];
      setCandidates(extracted); setConfirmed(merged); setStage('confirm');
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const confirmSave = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      await saveSymptoms(visitId, confirmed);
      const vitals = Object.fromEntries(Object.entries({ spo2: form.spo2, pulse: form.pulse, sbp: form.sbp, temp_c: form.temp_c }).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]));
      if (Object.keys(vitals).length) await addVitals(visitId, vitals);
      complete();
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  if (stage === 'confirm') {
    return (
      <section className="queue-panel intake-form">
        <div className="queue-head"><div><h2>Confirm symptoms</h2><p>Read back before saving. Low-confidence terms are highlighted. Nothing is saved until you confirm.</p></div></div>
        <form onSubmit={confirmSave}>
          <div className="wide">
            {confirmed.length ? confirmed.map((c) => {
              const meta = candidates.find((x) => x.canonical === c);
              const low = meta && meta.confidence < 0.8;
              return <button type="button" key={c} className="outline-button" style={low ? { borderColor: '#e85b5b', color: '#a23e36' } : undefined} onClick={() => setConfirmed(confirmed.filter((x) => x !== c))} title={low ? 'Low confidence — tap to remove' : 'Tap to remove'}>{c.replaceAll('_', ' ')}{low ? ' (check)' : ' ×'}</button>;
            }) : <p className="explain">No symptoms selected. Add from the picklist below.</p>}
          </div>
          <fieldset className="wide"><legend>Picklist fallback</legend>{symptoms.map((symptom) => <label className="check" key={symptom}><input type="checkbox" checked={confirmed.includes(symptom)} onChange={() => setConfirmed(confirmed.includes(symptom) ? confirmed.filter((x) => x !== symptom) : [...confirmed, symptom])} />{symptom.replaceAll('_', ' ')}</label>)}</fieldset>
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Confirm and add to queue'}</button>
        </form>
      </section>
    );
  }
  return (
    <section className="queue-panel intake-form">
      <div className="queue-head"><div><h2>Register patient</h2><p>Describe symptoms in your own words, then confirm before saving.</p></div></div>
      <form onSubmit={register}>
        <label>Full name<input required value={form.name} onChange={(e) => update('name', e.target.value)} /></label>
        <label>Date of birth<input type="date" value={form.date_of_birth} onChange={(e) => update('date_of_birth', e.target.value)} /></label>
        <label className="wide">Presenting complaint<textarea required value={form.complaint} onChange={(e) => update('complaint', e.target.value)} /></label>
        <label className="wide">Symptoms in your own words (English, Hindi, Marathi)<textarea value={form.freeText} onChange={(e) => update('freeText', e.target.value)} placeholder="e.g. mujhe bukhar aur khansi hai" /></label>
        <label>Language<select value={form.lang} onChange={(e) => update('lang', e.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="mr">Marathi</option></select></label>
        <div>{speechSupported ? <button type="button" className="outline-button" onClick={startVoice}>{listening ? 'Listening…' : 'Use voice input'}</button> : <p className="explain">Voice input is not supported in this browser. Use typing or the picklist below.</p>}{speechError && <p className="form-error">{speechError}</p>}</div>
        <fieldset className="wide"><legend>Symptoms picklist (fallback)</legend>{symptoms.map((symptom) => <label className="check" key={symptom}><input type="checkbox" checked={form.symptoms.includes(symptom)} onChange={() => update('symptoms', form.symptoms.includes(symptom) ? form.symptoms.filter((x) => x !== symptom) : [...form.symptoms, symptom])} />{symptom.replaceAll('_', ' ')}</label>)}</fieldset>
        <fieldset className="wide"><legend>Vitals (if known)</legend>{['spo2', 'pulse', 'sbp', 'temp_c'].map((key) => <label className="vital-input" key={key}>{key.replace('_', ' ')}<input type="number" step="any" value={form[key]} onChange={(e) => update(key, e.target.value)} /></label>)}</fieldset>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={saving}>{saving ? 'Registering…' : 'Review symptoms'}</button>
      </form>
    </section>
  );
}

export function App() {
  const [authed, setAuthed] = useState(() => Boolean(sessionStorage.getItem('medqueue_token')));
  const [role, setRole] = useState(() => getRole());
  const [user, setUser] = useState(() => getUser());
  const { queue, loading, error, refresh } = useQueue(authed);
  const [active, setActive] = useState('Queue');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('All patients');
  const [selectedId, setSelectedId] = useState(null);
  const [modal, setModal] = useState(false);
  const [level, setLevel] = useState(3);
  const [reason, setReason] = useState('');
  const [toast, setToast] = useState('');
  const [now, setNow] = useState(() => Date.now());
  const [doctors, setDoctors] = useState([]);
  const [audit, setAudit] = useState([]);
  const [auditError, setAuditError] = useState('');

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const loadDoctors = useCallback(async () => {
    if (!authed) return;
    try {
      setDoctors(await getDoctors());
    } catch {
      setDoctors([]);
    }
  }, [authed]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadDoctors();
  }, [loadDoctors, queue.length]);

  const selected = queue.find((item) => item.id === selectedId) || queue[0];
  const visible = useMemo(
    () => queue.filter((p) => (filter === 'All patients' || `Level ${p.triage.level}` === filter) && `${p.patient.name} ${p.complaint}`.toLowerCase().includes(query.toLowerCase())),
    [queue, filter, query],
  );
  const note = (text) => {
    setToast(text);
    setTimeout(() => setToast(''), 2800);
  };

  useEffect(() => {
    let cancelled = false;
    async function loadAudit() {
      if (!selected || role !== 'admin') {
        setAudit([]);
        setAuditError('');
        return;
      }
      try {
        const events = await getAudit(selected.id);
        if (!cancelled) {
          setAudit(events);
          setAuditError('');
        }
      } catch (err) {
        if (!cancelled) {
          setAudit([]);
          setAuditError(err.message);
        }
      }
    }
    loadAudit();
    return () => {
      cancelled = true;
    };
  }, [selected, role]);

  if (!authed) {
    return (
      <Login
        onLogin={(result) => {
          setAuthed(true);
          setRole(result.role || getRole());
          setUser(result.username || getUser());
          setActive('Queue');
        }}
      />
    );
  }

  const doOverride = async (event) => {
    event.preventDefault();
    await overrideVisit(selected.id, { level: Number(level), reason });
    setModal(false);
    setReason('');
    await refresh();
    note('Clinical override saved to the audit log.');
  };
  const review = async () => {
    await setStatus(selected.id, 'in_review');
    await refresh();
    note(`${selected.patient.name} marked as in review.`);
  };
  const changeDoctorStatus = async (id, next) => {
    await setDoctorStatus(id, next);
    await loadDoctors();
    note('Doctor status updated.');
  };
  const changeAssignment = async (visitId, doctorId) => {
    await assignDoctor(visitId, doctorId === '' ? null : Number(doctorId));
    await refresh();
    note('Doctor assignment saved.');
  };
  const signOut = () => {
    logout();
    setAuthed(false);
    setRole('');
    setUser('');
  };

  const redFlags = queue.filter((p) => p.triage.red_flag).length;
  const avg = queue.length ? Math.round(queue.reduce((sum, p) => sum + Math.max(0, (now - new Date(p.registered_at)) / 60000), 0) / queue.length) : 0;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top"><span className="brand-mark">M</span><span>MedQueue<em>AI</em></span></a>
        <p className="site-name">Civic General Hospital<br /><span>OPD · Ground floor</span></p>
        <nav>{['Queue', 'Intake'].map((item) => <button key={item} className={active === item ? 'nav-link active' : 'nav-link'} onClick={() => setActive(item)}><span>{item === 'Queue' ? '◉' : '＋'}</span>{item}</button>)}</nav>
        <section className="sidebar-foot"><div className="live-dot" /><div><strong>Live coordination</strong><small>{error ? 'API unavailable' : 'Refreshes every 5 seconds'}</small></div></section>
        <button className="profile" onClick={signOut} title="Sign out">
          <span className="avatar">{(user || role || 'U').slice(0, 2).toUpperCase()}</span>
          <span>{user || 'Clinical user'}<small>{role || 'Clinical user'} · Sign out</small></span>
        </button>
      </aside>
      <section className="workspace" id="top">
        <header className="topbar">
          <div><p className="breadcrumb">Today · {new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(new Date())}</p><h1>{active === 'Intake' ? 'Patient intake' : 'Live queue'}</h1></div>
          <button className="intake-button" onClick={() => setActive('Intake')}>Start intake <span>＋</span></button>
        </header>
        {error && <section className="alert" role="alert"><div className="alert-icon">!</div><div><strong>Demo mode — API unavailable</strong><p>Showing hardcoded synthetic patient records. Start the API to use live data.</p></div></section>}
        {active === 'Intake' ? <Intake complete={async () => { await refresh(); setActive('Queue'); note('Patient added and triaged.'); }} /> : (
          <>
            <section className="summary-grid">
              <article><span className="metric-icon blue">⌛</span><p>Waiting now</p><strong>{queue.length}</strong><small>{error ? 'Synthetic demo data' : 'Live API data'}</small></article>
              <article><span className="metric-icon amber">↗</span><p>Needs review</p><strong>{queue.filter((p) => p.triage.level <= 2).length}</strong><small>Level 1–2 patients</small></article>
              <article><span className="metric-icon coral">✦</span><p>Red-flag alerts</p><strong>{redFlags}</strong><small>Immediate nurse attention</small></article>
              <article><span className="metric-icon navy">⌁</span><p>Average wait</p><strong>{avg} <em>min</em></strong><small>From registration times</small></article>
            </section>
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
                  <button className={`patient ${selected?.id === p.id ? 'selected' : ''} ${p.triage.red_flag ? 'red-flag' : ''}`} onClick={() => setSelectedId(p.id)} key={p.id}>
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
            <section className="queue-panel">
              <div className="queue-head"><div><h2>Doctors</h2><p>Status controls affect wait estimates.</p></div></div>
              <div className="patient-list">
                {doctors.length ? doctors.map((d) => (
                  <div className="patient" key={d.id}>
                    <span className="rank">D{d.id}</span>
                    <span className="person"><b>{d.name}</b><small>{d.department} · ~{d.avg_consult_min} min</small></span>
                    <span className="complaint">{d.status}</span>
                    <span className="factors">{d.status === 'available' ? 'Taking patients' : d.status}</span>
                    <span className="eta">
                      <select value={d.status} onChange={(e) => changeDoctorStatus(d.id, e.target.value)}>
                        <option value="available">available</option>
                        <option value="break">break</option>
                        <option value="off">off</option>
                      </select>
                    </span>
                    <span className="chevron">›</span>
                  </div>
                )) : <p className="empty-state">No doctors found.</p>}
              </div>
            </section>
          </>
        )}
      </section>
      <aside className="detail-panel">
        {selected ? (
          <>
            <div className="detail-head"><span>Patient brief</span></div>
            <div className={`level-banner l${selected.triage.level}`}><span>Urgency level {selected.triage.level}</span><b>{selected.triage.red_flag ? 'Immediate assessment' : 'Priority review'}</b></div>
            <section className="patient-title"><div className="initials">{selected.patient.name.split(' ').map((x) => x[0]).join('')}</div><div><h2>{selected.patient.name}</h2><p>#{selected.id} · {age(selected.patient.date_of_birth)} years</p></div></section>
            <section className="detail-section">
              <h3>Reason for position</h3>
              <p className="explain">{selected.triage.factors.join('. ') || 'Priority uses triage level and time already waiting.'}</p>
              {selected.triage.source === 'model' && selected.triage.top_factors && (
                <p className="explain">Model {selected.triage.model_version}: {selected.triage.top_factors.map((f) => `${f.name.replaceAll('_', ' ')} ${f.value}`).join(', ')}.</p>
              )}
              {selected.triage.source === 'stub' && <p className="explain">AI unavailable — using rules and stub triage (pending clinical review).</p>}
              {selected.triage.source === 'rules' && <p className="explain">Red-flag rule applied (rules-first, pending clinical review).</p>}
              <p className="explain">Expected review: {expectedReview(selected)} ({expectedSub(selected)}).</p>
            </section>
            <section className="detail-section vitals">
              <h3>Latest vitals</h3>
              <div>{Object.entries(selected.latest_vitals).length ? Object.entries(selected.latest_vitals).map(([key, value]) => <p key={key}><span>{key.replace('_', ' ')}</span><b>{value}</b></p>) : <p>No vitals recorded.</p>}</div>
            </section>
            <section className="detail-section">
              <h3>Doctor</h3>
              <select value={selected.doctor_id ?? ''} onChange={(e) => changeAssignment(selected.id, e.target.value)}>
                <option value="">Unassigned</option>
                {doctors.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.status})</option>)}
              </select>
            </section>
            {role === 'admin' && (
              <section className="detail-section">
                <h3>Audit log (admin only)</h3>
                {auditError ? <p className="explain">{auditError}</p> : audit.length ? audit.map((event) => <p className="explain" key={event.id}>#{event.id} {event.action} by {event.actor}</p>) : <p className="explain">No audit events.</p>}
              </section>
            )}
            <section className="staff-note">
              <p>Human judgment is final. This is decision support, not a diagnosis.</p>
              <button className="outline-button" onClick={() => { setLevel(selected.triage.level); setModal(true); }}>Override priority</button>
              <button className="primary-button" onClick={review}>Begin review</button>
            </section>
          </>
        ) : <p className="empty-state">Select a patient from the queue.</p>}
      </aside>
      {modal && <div className="modal-backdrop"><form className="modal" onSubmit={doOverride}><button type="button" className="modal-close" onClick={() => setModal(false)}>×</button><p className="modal-kicker">Clinical override</p><h2>Set a new priority</h2><label>Urgency level<select value={level} onChange={(e) => setLevel(e.target.value)}>{[1, 2, 3, 4, 5].map((x) => <option key={x} value={x}>Level {x}</option>)}</select></label><label>Override reason<textarea required minLength="3" value={reason} onChange={(e) => setReason(e.target.value)} /></label><div className="modal-actions"><button type="button" onClick={() => setModal(false)}>Cancel</button><button className="primary-button">Save override</button></div></form></div>}
      {toast && <div className="toast" role="status">✓ {toast}</div>}
    </main>
  );
}
createRoot(document.getElementById('root')).render(<App />);
