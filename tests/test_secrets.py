import json
import os

import boto3

from actioncloud.secrets import load_secret_environment


def test_secrets_manager_loads_multiple_secrets_without_overriding_env(monkeypatch):
    payloads = {
        "database": {"username": "master", "password": "master-pass", "host": "db.example", "port": 5432},
        "application": {
            "db_user": "app",
            "db_password": "app-pass",
            "actioncloud_admin_key": "admin-key",
            "prometheus_metrics_token": "metrics-token",
        },
    }

    class FakeSecretsManager:
        def get_secret_value(self, *, SecretId):
            return {"SecretString": json.dumps(payloads[SecretId])}

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: FakeSecretsManager())
    monkeypatch.setenv("AWS_SECRETS_MANAGER_ARN", "database,application")
    monkeypatch.setenv("DB_PASSWORD", "explicit-local-password")

    loaded = load_secret_environment()

    assert loaded["DB_USER"] == "app"
    assert loaded["DB_PASSWORD"] == "app-pass"
    assert loaded["ACTIONCLOUD_ADMIN_KEY"] == "admin-key"
    assert loaded["PROMETHEUS_METRICS_TOKEN"] == "metrics-token"
    assert os.environ["DB_PASSWORD"] == "explicit-local-password"
