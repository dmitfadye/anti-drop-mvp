# Анти-Дроп — P1: качественный слой коммуникации.
# Не обещает production-банковский runtime: это синтетический демонстратор.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ANTI_DROP_DEMO_MODE=true \
    ANTI_DROP_LOCALIZATION_ENABLED=true \
    ANTI_DROP_OPERATOR_UI_ENABLED=false \
    ANTI_DROP_EXPERIMENT_ENABLED=false \
    ANTI_DROP_ADVISORY_ENABLED=false

WORKDIR /app

# zoneinfo needs tzdata on slim images; the detector reads Europe/Moscow.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py models.py app_stdlib.py pyproject.toml ./
COPY src/ ./src/
COPY anti_drop_ml/ ./anti_drop_ml/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY locales/ ./locales/
COPY templates/ ./templates/
COPY fixtures/ ./fixtures/
COPY configs/ ./configs/

# Reports are produced at run time into a volume; nothing pre-baked.
RUN mkdir -p /app/reports /app/.local \
    && useradd --create-home --uid 10001 sandbox \
    && chown -R sandbox:sandbox /app
USER sandbox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]