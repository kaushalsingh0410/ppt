#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL..."
until python - <<'EOF'
import psycopg2, os, sys
try:
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
    )
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"  DB not ready: {e}")
    sys.exit(1)
EOF
do
  sleep 2
done

echo "==> PostgreSQL is ready."

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting FastAPI + Streamlit via supervisord..."
mkdir -p /var/log/supervisor
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf