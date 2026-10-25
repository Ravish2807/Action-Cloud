FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /app

RUN groupadd --system --gid 10001 actioncloud \
    && useradd --system --uid 10001 --gid actioncloud --no-create-home --home-dir /tmp actioncloud

COPY pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-deps . \
    && python -m pip install -r dashboard/requirements.txt boto3==1.35.81

USER actioncloud
EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
