export const symptoms = ['chest_pain', 'chest_tightness', 'breathlessness', 'fever', 'dizziness', 'abdominal_pain', 'cough'];
export const age = (dob) => (dob ? new Date().getFullYear() - new Date(dob).getFullYear() : '—');
export const waitedMin = (p) => Math.max(0, Math.round((Date.now() - new Date(p.registered_at)) / 60000));
export const expectedReview = (p) => {
  if (p.est_wait_min === null || p.est_wait_min === undefined) return p.triage.red_flag ? 'Now' : `${waitedMin(p)} min`;
  if (p.triage.red_flag && p.est_wait_min === 0) return 'Now';
  return `~${p.est_wait_min} min`;
};
export const expectedSub = (p) => {
  if (p.est_wait_min === null || p.est_wait_min === undefined) return p.triage.red_flag ? 'Nurse now' : 'waiting';
  if (p.triage.red_flag && p.est_wait_min === 0) return 'Nurse now';
  return 'estimated';
};
export function beep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.value = 0.08;
    osc.start();
    osc.stop(ctx.currentTime + 0.25);
  } catch {
    /* audio is optional */
  }
}
