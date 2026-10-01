# MedQueueAI

MedQueueAI is a prototype for an explainable, severity-aware OPD queue. It includes a staff dashboard prototype and a FastAPI backend for patient registration, visit triage, queue ordering, clinical overrides, and audit events.

> **Safety note:** MedQueueAI is decision support for queue ordering, not a diagnostic tool. The priority weights and red-flag rules are engineering drafts pending clinical review and must not be used outside a prototype.

## Repository layout

- `frontend/` — Vite + React staff dashboard prototype.
- `backend/app/` — FastAPI application, SQLite persistence, RBAC, and audit trail.
- `backend/app/queue/` — pure priority and wait-estimation logic.
- `backend/app/triage/` — config-driven draft red-flag evaluator and triage stub.
- `backend/tests/` — unit tests for the engine.
- `docs/red_flag_rules.yaml` — clinician-reviewable draft red-flag rules.
- `ml/` and `simulation/` — reserved for future model training and queue simulation work.

## Run the frontend

```bash
cd frontend
npm ci
npm run dev
```

Create a production bundle and run static checks with:

```bash
npm run lint
npm run build
```

The dashboard remains a static prototype; the API can be explored at `http://localhost:8000/docs`.

## Run the backend engine tests

Install the pinned dependencies, then run:

```bash
cd backend
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

The development account is `triage` / `medqueue-demo`. Obtain a bearer token from
`POST /auth/login`, then use it for protected endpoints. The default SQLite database is
`backend/medqueue.db`; set `MEDQUEUE_DATABASE_URL` and `MEDQUEUE_JWT_SECRET` for another
environment. Development credentials must be replaced before any non-prototype deployment.

## Development workflow

GitHub Actions runs the frontend lint/build and backend Ruff/pytest checks for pushes and pull requests. The root `docker-compose.yml` starts the API:

```bash
docker compose up --build
```
