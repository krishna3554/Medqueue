import { useEffect, useState } from 'react';
import { getProfile } from '../api';

export function ProfileView({ user, role }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { let active = true; getProfile().then((data) => active && setProfile(data)).catch((err) => active && setError(err.message)); return () => { active = false; }; }, []);
  return <section className="feature-page"><div className="feature-heading"><span className="eyebrow">Account</span><h2>Your profile</h2><p>Role-aware workspace settings for the current signed-in session.</p></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="profile-card"><div className="profile-hero"><span className="profile-large-avatar">{(user || 'U').slice(0, 2).toUpperCase()}</span><div><h3>{profile?.username || user || 'Signed-in user'}</h3><p>{profile?.role || role} · {profile?.department || 'Hospital operations'}</p></div></div><dl><div><dt>Role</dt><dd>{profile?.role || role}</dd></div><div><dt>Department</dt><dd>{profile?.department || 'Hospital operations'}</dd></div><div><dt>Availability</dt><dd>{profile?.availability_status || 'Not applicable'}</dd></div><div><dt>Notifications</dt><dd>{profile?.notifications_enabled ? 'Enabled' : 'Disabled'}</dd></div></dl></div>
    <div className="safety-card"><strong>Decision support only</strong><p>MedQueueAI does not diagnose patients. Human judgment remains final, and clinical overrides are audited.</p></div>
  </section>;
}
