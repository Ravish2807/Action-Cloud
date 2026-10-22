"""Load application settings from AWS Secrets Manager when configured.

Local development remains dotenv-based. In AWS, set
``AWS_SECRETS_MANAGER_ARN`` to an RDS-managed JSON secret or a JSON object of
environment variable names. Explicit environment variables take precedence.
"""

from __future__ import annotations

import json
import os
from typing import Any


_RDS_KEY_MAP = {
    "username": "DB_USER",
    "password": "DB_PASSWORD",
    "db_user": "DB_USER",
    "db_password": "DB_PASSWORD",
    "host": "DB_HOST",
    "port": "DB_PORT",
    "dbname": "DB_NAME",
    "actioncloud_admin_key": "ACTIONCLOUD_ADMIN_KEY",
    "prometheus_metrics_token": "PROMETHEUS_METRICS_TOKEN",
}


def _environment_values(secret: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in secret.items():
        env_key = _RDS_KEY_MAP.get(key, key)
        if value is not None and isinstance(value, (str, int, float, bool)):
            values[env_key] = str(value)
    return values


def load_secret_environment() -> dict[str, str]:
    """Read a configured Secrets Manager JSON secret into missing env vars.

    Returns the values loaded (without logging them), or an empty mapping when
    ``AWS_SECRETS_MANAGER_ARN`` is unset. A configured but unreadable secret is
    a startup error so the service cannot silently use local fallback values.
    """
    secret_ids = [item.strip() for item in os.environ.get("AWS_SECRETS_MANAGER_ARN", "").split(",") if item.strip()]
    if not secret_ids:
        return {}

    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION"))
    loaded: dict[str, str] = {}
    for secret_id in secret_ids:
        try:
            response = client.get_secret_value(SecretId=secret_id)
            raw_secret = response.get("SecretString")
            if raw_secret is None:
                binary = response.get("SecretBinary")
                raw_secret = binary.decode("utf-8") if isinstance(binary, bytes) else str(binary or "")
            payload = json.loads(raw_secret)
            if not isinstance(payload, dict):
                raise ValueError("secret JSON must be an object")
            loaded.update(_environment_values(payload))
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Unable to load the configured ActionCloud Secrets Manager secret") from exc

    for key, value in loaded.items():
        os.environ.setdefault(key, value)
    return loaded
