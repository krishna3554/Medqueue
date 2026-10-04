# MedQueueAI

MedQueueAI is an explainable, severity-aware OPD triage and queue prototype.
It ranks waiting patients by clinical urgency plus waiting time, keeps
red-flag rules above any model output, and records every human override in an
audit log.

> **Safety note:** decision support only, not diagnosis. All red-flag rules,
> queue weights, model outputs, lexicon entries, and simulation numbers are
> engineering drafts pending clinical review. No real patient data is used
> anywhere — only public data or clearly labelled synthetic data. Never use
> this prototype for care decisions.

## Architecture

```mermaid
flowchart LR
    UI[Vite + React dashboard<br/>login, intake, queue, doctors, audit] -->|REST + WS queue| API
    API[FastAPI backend<br/>auth RBAC, visits, triage, wait estimates] --> DB[(SQLite / PostgreSQL)]
    API --> RULES[docs/red_flag_rules.yaml<br/>rules-first triage]
    API --> MODEL[ml/artifacts<br/>synthetic XGBoost + SHAP<br/>fallback to stub]
    API --> NLP[backend/app/nlp<br/>hi/mr lexicon extract-then-confirm]
    SIM[simulation/opd_sim.py<br/>SimPy FCFS vs severity vs MedQueueAI] --> RES[docs/results<br/>CSVs, PNGs, tuning.md]
    WS["/ws/queue<br/>JWT-checked live queue + red-flag alerts"] --> UI
```

## One-command start

```bash
docker compose up --build
```

- Dashboard: `http://localhost:5173` (serves the production build).
- API: `http://localhost:8000` (`/docs`, `/health`, `/queue`, `/ws/queue`).
- Seed synthetic demo data (dev users, doctors, demo patients):

```bash
docker compose exec backend python -m app.seed
```

Dev logins (password `medqueue-demo`): `registration`, `nurse`
(triage_nurse), `clinician`, `admin`.

PostgreSQL option:

```bash
docker compose --profile postgres up --build
export MEDQUEUE_DATABASE_URL=postgresql://medqueue:medqueue@localhost:5432/medqueue
```

## Local development

```bash
cd backend
python -m pip install -e '.[dev]'
ruff check .
pytest
cd ../frontend
npm ci
npm run lint
npm test
npm run build
npm run dev
```

ML and simulation (synthetic only):

```bash
pip install -r ml/requirements.txt
PYTHONPATH=ml python ml/train.py
PYTHONPATH=ml python ml/evaluate.py
PYTHONPATH=. python -m simulation.run --seeds 30
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://localhost:8000` | API base URL baked into the frontend build |
| `MEDQUEUE_DATABASE_URL` | `sqlite:///./medqueue.db` | SQLAlchemy URL (SQLite file or `postgresql://…`) |
| `MEDQUEUE_JWT_SECRET` | `development-secret-change-me` | JWT signing secret (replace outside local work) |
| `MEDQUEUE_CORS_ORIGINS` | `http://localhost:5173` | Allowed browser origins, comma-separated |
| `MEDQUEUE_RULES_PATH` | `…/docs/red_flag_rules.yaml` | Red-flag rules file |
| `MEDQUEUE_MODEL_DIR` | `ml/artifacts` (`/ml/artifacts` in Docker) | Model binaries; when absent the API reports "AI unavailable" |

## API summary

| Method & path | Role | Notes |
|---------------|------|-------|
| `POST /auth/login` | public | Seeded dev users only; returns JWT + role |
| `POST /patients`, `POST /visits` | any signed-in | Registration never blocked by the model |
| `POST /visits/{id}/vitals`, `POST /visits/{id}/symptoms` | any signed-in | Re-runs rules-first triage; symptoms save only after confirmation |
| `POST /visits/{id}/symptoms/extract` | any signed-in | Draft hi/mr lexicon candidates; never saves |
| `GET /queue` | any signed-in | Priority-ranked, with `est_wait_min` per visit |
| `GET /ws/queue?token=…` | JWT query param | Live queue snapshots + `red_flag_alert` every 5s; polling fallback |
| `POST /visits/{id}/override` | triage_nurse, clinician, admin | Human override is final; audited |
| `PATCH /visits/{id}/status`, `PATCH /visits/{id}/doctor` | triage_nurse, clinician, admin | Status changes record consult start/end for wait estimates |
| `GET /doctors`, `PATCH /doctors/{id}/status` | any / clinical | Status controls affect wait estimates |
| `GET /visits/{id}/audit` | admin | Override/escalation trail viewer |

Rules-first: a matching red-flag rule always overrides any model output.
Override replaces the base level while red-flag and aging still apply.

## Screenshots

Dashboard views (run `docker compose up --build` and open
`http://localhost:5173`):

- **Live queue** — priority-ordered list with "Expected review"
  (`est_wait_min`), red-flag banner with optional audible cue, and live
  WebSocket status (polling fallback when unavailable).
- **Patient intake** — free-text plus voice input (en/hi/mr), extraction
  read-back with editable chips and low-confidence highlights, picklist
  fallback, then vitals.
- **Patient brief** — reason for position (rule name, model top-3 factors,
  or "AI unavailable"), doctor assignment, and an admin-only audit log.

Quantitative evidence (synthetic only): see
`docs/results/wait_by_level.png` (mean wait by urgency level per policy),
`docs/results/model_evaluation.md`, `docs/results/nlp_evaluation.md`, and
`docs/results/tuning.md`.

## Docs

- `docs/DEMO.md` — three scripted scenarios (routine, urgent overtaking,
  red-flag walk-in).
- `docs/clinical_review.md` — every rule and weight needing sign-off.
- `ml/DATA_CARD.md`, `ml/MODEL_CARD.md` — synthetic-only data and model.
- `docs/red_flag_rules.yaml`, `docs/vocabulary.csv` — drafts needing
  native-speaker/clinician review.
