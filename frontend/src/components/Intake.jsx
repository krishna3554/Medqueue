import { useState } from 'react';
import { addVitals, createPatient, createVisit, extractSymptoms, saveSymptoms } from '../api';
import { symptoms } from '../queueUtils';

export function Intake({ complete }) {
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
