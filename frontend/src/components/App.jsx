/* eslint-disable no-unused-vars -- JSX-only imports are flagged without the React plugin */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  assignDoctor,
  getAudit,
  getDoctors,
  getRole,
  getUser,
  logout,
  overrideVisit,
  setDoctorStatus,
  setStatus,
} from '../api';
import { useQueue } from '../useQueue';
import { beep } from '../queueUtils';
import { AlertBanner } from './AlertBanner';
import { Intake } from './Intake';
import { Login } from './Login';
import { OverrideModal } from './OverrideModal';
import { PatientPanel } from './PatientPanel';
import { QueueList } from './QueueList';
import { SummaryCards } from './SummaryCards';
import { Toast } from './Toast';

export function App() {
  const [authed, setAuthed] = useState(() => Boolean(sessionStorage.getItem('medqueue_token')));
  const [role, setRole] = useState(() => getRole());
  const [user, setUser] = useState(() => getUser());
  const { queue, loading, error, refresh, live, alert } = useQueue(authed);
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
  const [soundOn, setSoundOn] = useState(false);
  const lastAlertRef = useRef(0);

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

  useEffect(() => {
    if (alert && soundOn && alert.at !== lastAlertRef.current) {
      lastAlertRef.current = alert.at;
      beep();
    }
  }, [alert, soundOn]);

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
  const openOverride = () => {
    setLevel(selected.triage.level);
    setModal(true);
  };

  const redFlags = queue.filter((p) => p.triage.red_flag).length;
  const avg = queue.length ? Math.round(queue.reduce((sum, p) => sum + Math.max(0, (now - new Date(p.registered_at)) / 60000), 0) / queue.length) : 0;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top"><span className="brand-mark">M</span><span>MedQueue<em>AI</em></span></a>
        <p className="site-name">Civic General Hospital<br /><span>OPD · Ground floor</span></p>
        <nav>{['Queue', 'Intake'].map((item) => <button key={item} className={active === item ? 'nav-link active' : 'nav-link'} onClick={() => setActive(item)}><span>{item === 'Queue' ? '◉' : '＋'}</span>{item}</button>)}</nav>
        <section className="sidebar-foot"><div className="live-dot" /><div><strong>Live coordination</strong><small>{error ? 'API unavailable' : live ? 'Live via WebSocket' : 'Refreshes every 5 seconds'}</small></div></section>
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
        <AlertBanner count={redFlags} live={live} soundOn={soundOn} onToggleSound={() => setSoundOn(!soundOn)} latestIds={alert?.ids} />
        {error && <section className="alert" role="alert"><div className="alert-icon">!</div><div><strong>Demo mode — API unavailable</strong><p>Showing hardcoded synthetic patient records. Start the API to use live data.</p></div></section>}
        {active === 'Intake' ? <Intake complete={async () => { await refresh(); setActive('Queue'); note('Patient added and triaged.'); }} /> : (
          <>
            <SummaryCards queue={queue} avg={avg} error={error} />
            <QueueList visible={visible} selectedId={selected?.id} onSelect={setSelectedId} loading={loading} query={query} setQuery={setQuery} filter={filter} setFilter={setFilter} />
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
        <PatientPanel
          selected={selected}
          doctors={doctors}
          role={role}
          audit={audit}
          auditError={auditError}
          onOverride={openOverride}
          onReview={review}
          onAssign={changeAssignment}
        />
      </aside>
      {modal && <OverrideModal level={level} setLevel={setLevel} reason={reason} setReason={setReason} onSubmit={doOverride} onClose={() => setModal(false)} />}
      <Toast toast={toast} />
    </main>
  );
}
