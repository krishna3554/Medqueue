// SYNTHETIC DEMO DATA ONLY — mirrors backend/app/seed.py DEMO_PATIENTS.
// Clearly synthetic, never real patient data. Used only when the API is
// unavailable. Triage levels here are illustrative; live triage comes from
// the rules-first backend (rules, then model, then stub).
const minutesAgo = (minutes) => new Date(Date.now() - minutes * 60_000).toISOString();

export const demoQueue = [
  {
    id: 1001,
    patient: { id: 101, name: 'Demo Anita Rao', date_of_birth: '1968-04-12' },
    complaint: 'Chest tightness and breathlessness', symptoms: ['chest_tightness', 'breathlessness'],
    registered_at: minutesAgo(3), status: 'waiting', latest_vitals: { spo2: 91, pulse: 118, sbp: 148, temp_c: 37.2 },
    triage: { level: 1, automated_level: 1, red_flag: true, factors: ['Chest symptoms with low oxygen', 'Chest pain with breathlessness'], source: 'rules', overridden: false }, priority_score: 1.95,
  },
  {
    id: 1002,
    patient: { id: 102, name: 'Demo Farhan Khan', date_of_birth: '1995-09-20' },
    complaint: 'High fever for three days', symptoms: ['fever'], registered_at: minutesAgo(11), status: 'waiting', latest_vitals: { temp_c: 39.4, pulse: 112 },
    triage: { level: 2, automated_level: 2, red_flag: false, factors: ['High temperature', 'Elevated pulse'], source: 'stub', overridden: false }, priority_score: 0.54,
  },
  {
    id: 1003,
    patient: { id: 103, name: 'Demo Meera Shah', date_of_birth: '1984-01-08' },
    complaint: 'Severe abdominal pain', symptoms: ['abdominal_pain'], registered_at: minutesAgo(19), status: 'waiting', latest_vitals: { pulse: 106, sbp: 124 },
    triage: { level: 3, automated_level: 3, red_flag: false, factors: ['Reported abdominal pain'], source: 'stub', overridden: false }, priority_score: 0.37,
  },
  {
    id: 1004,
    patient: { id: 104, name: 'Demo Gaurav Patel', date_of_birth: '1959-07-15' },
    complaint: 'Dizziness', symptoms: ['dizziness'], registered_at: minutesAgo(27), status: 'waiting', latest_vitals: { sbp: 178, pulse: 84 },
    triage: { level: 3, automated_level: 3, red_flag: false, factors: ['Elevated blood pressure'], source: 'stub', overridden: false }, priority_score: 0.42,
  },
  {
    id: 1005,
    patient: { id: 105, name: 'Demo Kavita Joshi', date_of_birth: '2002-11-03' },
    complaint: 'Persistent cough', symptoms: ['cough'], registered_at: minutesAgo(36), status: 'waiting', latest_vitals: { spo2: 98, temp_c: 37.2 },
    triage: { level: 4, automated_level: 4, red_flag: false, factors: ['No red flags identified'], source: 'stub', overridden: false }, priority_score: 0.21,
  },
  {
    id: 1006,
    patient: { id: 106, name: 'Demo Joseph Dsouza', date_of_birth: '1976-03-25' },
    complaint: 'Medication refill', symptoms: [], registered_at: minutesAgo(48), status: 'waiting', latest_vitals: {},
    triage: { level: 5, automated_level: 5, red_flag: false, factors: ['No red flags identified'], source: 'stub', overridden: false }, priority_score: 0.24,
  },
];
