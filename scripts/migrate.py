"""Apply the SQL schema files in numeric order using DATABASE_URL/DB_* settings."""

from __future__ import annotations

import logging
import json
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from actioncloud.config import settings

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    files = sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise SystemExit(f"No SQL migrations found under {SQL_DIR}")

    master_secret_arn = os.environ.get("AWS_MIGRATION_MASTER_SECRET_ARN")
    if master_secret_arn:
        import boto3

        response = boto3.client("secretsmanager", region_name=settings.aws_region).get_secret_value(
            SecretId=master_secret_arn
        )
        master = json.loads(response["SecretString"])
        dsn = make_conninfo(
            # RDS-managed master secrets contain username/password only; the
            # endpoint and database name are supplied by the deployment config.
            host=master.get("host", settings.db_host),
            port=master.get("port", settings.db_port),
            dbname=master.get("dbname", settings.db_name),
            user=master["username"], password=master["password"], sslmode="require",
        )
        runtime_role = settings.db_user
        runtime_password = settings.db_password
    else:
        if os.environ.get("AWS_SECRETS_MANAGER_ARN"):
            raise SystemExit("AWS_MIGRATION_MASTER_SECRET_ARN is required for managed database migrations")
        dsn = settings.dsn
        runtime_role = runtime_password = ""

    with psycopg.connect(dsn) as conn:
        for path in files:
            logging.info("Applying %s", path.name)
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"), prepare=False)
        if runtime_role:
            with conn.transaction():
                _grant_runtime_access(conn, runtime_role, runtime_password, settings.db_name, master["username"])
    logging.info("Applied %d schema files", len(files))
    return 0


def _grant_runtime_access(
    conn: psycopg.Connection, role_name: str, password: str, database_name: str, owner_name: str
) -> None:
    """Keep app DML separate from the RDS master account used for migrations."""
    role = sql.Identifier(role_name)
    if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,)).fetchone():
        conn.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(role, sql.Literal(password)))
    else:
        conn.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(role, sql.Literal(password)))

    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database_name), role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(sql.Identifier(owner_name), role))
    conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}").format(sql.Identifier(owner_name), role))


if __name__ == "__main__":
    raise SystemExit(main())
