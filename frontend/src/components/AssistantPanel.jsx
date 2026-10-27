import { useState } from 'react';
import { askAssistant } from '../api';

export function AssistantPanel({ selected, role, onClose }) {
  const [question, setQuestion] = useState('Why is this patient ranked here?');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const clinical = ['triage_nurse', 'clinician', 'admin'].includes(role);
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true); setError('');
    try {
      const result = await askAssistant(question, clinical ? selected?.id : null);
      setAnswer(result.answer); setSources(result.sources || []);
    } catch (err) { setError(err.message || 'Assistant unavailable.'); }
    finally { setLoading(false); }
  };
  return (
    <section className="assistant-panel" aria-label="Read-only queue assistant">
      <div className="assistant-head"><div><span className="eyebrow">Read-only assistant</span><h2>Explain the queue</h2></div><button className="icon-button" onClick={onClose} aria-label="Close assistant">×</button></div>
      <p className="assistant-disclosure">Non-diagnostic. It explains recorded rules and model factors; it cannot change triage or save symptoms.</p>
      <form onSubmit={submit}>
        <label className="sr-only" htmlFor="assistant-question">Ask a question</label>
        <textarea id="assistant-question" value={question} onChange={(e) => setQuestion(e.target.value)} rows="3" placeholder="Ask about queue policy or this patient's position" />
        <button className="primary-button" disabled={loading || !question.trim()}>{loading ? 'Checking…' : 'Ask assistant'}</button>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {answer && <div className="assistant-answer" role="status"><strong>Explanation</strong><p>{answer}</p><small>Sources: {sources.join(' · ')}</small></div>}
    </section>
  );
}
