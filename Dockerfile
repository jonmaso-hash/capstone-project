# syntax=docker/dockerfile:1

# ---- Builder stage: install Python dependencies ----
FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Final stage: runtime image ----
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY . .

RUN chown -R appuser:appuser /app \
    && chmod +x docker-entrypoint.sh
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

EXPOSE 8000

# collectstatic needs real secrets (SECRET_KEY etc.) that only exist at
# container runtime, not at `docker build` time — see docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
