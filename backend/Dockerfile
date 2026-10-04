FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir bcrypt==4.3.0 fastapi==0.128.0 joblib==1.4.2 pandas==2.2.3 PyJWT==2.10.1 PyYAML==6.0.3 scikit-learn==1.7.1 shap==0.48.0 SQLAlchemy==2.0.45 "uvicorn[standard]==0.40.0" xgboost==3.0.2
COPY backend/app ./app
COPY docs/red_flag_rules.yaml /docs/red_flag_rules.yaml
COPY ml/artifacts/metadata.json /ml/artifacts/metadata.json
COPY ml/artifacts/model.joblib /ml/artifacts/model.joblib
COPY ml/artifacts/medians.joblib /ml/artifacts/medians.joblib
COPY ml/artifacts/features.joblib /ml/artifacts/features.joblib
ENV MEDQUEUE_RULES_PATH=/docs/red_flag_rules.yaml
ENV MEDQUEUE_MODEL_DIR=/ml/artifacts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
