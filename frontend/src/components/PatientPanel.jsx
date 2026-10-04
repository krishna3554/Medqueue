/* eslint-disable no-unused-vars -- JSX-only import flagged without the React plugin */
import { age, expectedReview, expectedSub } from '../queueUtils';
import { AuditLog } from './AuditLog';

export function PatientPanel({ selected, doctors, role, audit, auditError, onOverride, onReview, onAssign }) {
  if (!selected) return <p className="empty-state">Select a patient from the queue.</p>;
  return (
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
        <select value={selected.doctor_id ?? ''} onChange={(e) => onAssign(selected.id, e.target.value)}>
          <option value="">Unassigned</option>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.status})</option>)}
        </select>
      </section>
      {role === 'admin' && <AuditLog audit={audit} auditError={auditError} />}
      <section className="staff-note">
        <p>Human judgment is final. This is decision support, not a diagnosis.</p>
        <button className="outline-button" onClick={onOverride}>Override priority</button>
        <button className="primary-button" onClick={onReview}>Begin review</button>
      </section>
    </>
  );
}
