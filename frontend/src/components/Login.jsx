import { useState } from 'react';
import { login } from '../api';

export function Login({ onLogin }) {
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
