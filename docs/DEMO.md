# Demo script (synthetic data only)

Status: draft, pending clinical review. Decision support only, not diagnosis.
All patients below are clearly synthetic. Start with a seeded database:

```bash
docker compose up --build -d
docker compose exec backend python -m app.seed
```

Dev logins (password `medqueue-demo` for all): `registration`, `nurse`
(triage_nurse), `clinician`, `admin`. Get a token once:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"nurse","password":"medqueue-demo"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"
```

## Scenario 1 — routine patient (cough, joins the back of the queue)

```bash
PID=$(curl -s -X POST http://localhost:8000/patients -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"name":"Demo Routine"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
VID=$(curl -s -X POST http://localhost:8000/visits -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"patient_id\":$PID,\"complaint\":\"Persistent cough\",\"symptoms\":[\"cough\"]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s "http://localhost:8000/queue" -H "$AUTH" \
  | python3 -c "import sys,json; [print(r['id'], r['triage']['level'], r['est_wait_min']) for r in json.load(sys.stdin)]"
```

Expected: level 4–5, no red flag, `est_wait_min` reflects work ahead;
dashboard shows the patient near the bottom in "Priority order".

## Scenario 2 — urgent patient overtaking (high fever, moves ahead)

```bash
PID2=$(curl -s -X POST http://localhost:8000/patients -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Urgent","date_of_birth":"1995-09-20"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
VID2=$(curl -s -X POST http://localhost:8000/visits -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"patient_id\":$PID2,\"complaint\":\"High fever\",\"symptoms\":[\"fever\"]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST "http://localhost:8000/visits/$VID2/vitals" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"values":{"temp_c":39.4,"pulse":112}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['triage'])"
curl -s "http://localhost:8000/queue" -H "$AUTH" \
  | python3 -c "import sys,json; [print(r['id'], r['triage']['level']) for r in json.load(sys.stdin)]"
```

Expected: model or stub triage raises the level (often 2), so the urgent
visit outranks the routine one without any manual override. The
"Reason for position" panel shows the rationale or "AI unavailable".

## Scenario 3 — red-flag walk-in (chest pain + breathlessness, immediate)

```bash
PID3=$(curl -s -X POST http://localhost:8000/patients -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"name":"Demo RedFlag"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST http://localhost:8000/visits -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"patient_id\":$PID3,\"complaint\":\"Chest pain and breathlessness\",\"symptoms\":[\"chest_pain\",\"breathlessness\"]}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['triage'])"
```

Expected: rules-first triage returns level 1, `red_flag: true`,
`source: "rules"` even if the model disagrees. The dashboard shows the
red-flag banner (with optional sound) and the visit jumps to the top.
A clinician override stays final and is written to
`GET /visits/{id}/audit` (admin role required to read).
