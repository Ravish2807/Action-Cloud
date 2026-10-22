FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system --gid 10001 actioncloud \
    && useradd --system --uid 10001 --gid actioncloud --no-create-home --home-dir /app actioncloud

COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY scripts/migrate.py ./scripts/migrate.py

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER actioncloud
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "actioncloud.api:app", "--host", "0.0.0.0", "--port", "8000"]
