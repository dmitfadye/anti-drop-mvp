FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt \
    && useradd --create-home --uid 10001 antidrop
COPY --chown=antidrop:antidrop main.py models.py alembic.ini ./
COPY --chown=antidrop:antidrop src ./src
COPY --chown=antidrop:antidrop anti_drop_ml ./anti_drop_ml
COPY --chown=antidrop:antidrop migrations ./migrations
COPY --chown=antidrop:antidrop scripts ./scripts
COPY --chown=antidrop:antidrop data ./data
COPY --chown=antidrop:antidrop locales ./locales
COPY --chown=antidrop:antidrop templates ./templates
COPY --chown=antidrop:antidrop configs ./configs
COPY --chown=antidrop:antidrop static ./static
USER antidrop
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
