FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir fastapi==0.128.0 PyJWT==2.10.1 PyYAML==6.0.3 SQLAlchemy==2.0.45 "uvicorn[standard]==0.40.0"
COPY backend/app ./app
COPY docs/red_flag_rules.yaml /docs/red_flag_rules.yaml
ENV MEDQUEUE_RULES_PATH=/docs/red_flag_rules.yaml

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
