#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Running database migrations..."
    alembic -c /app/alembic.ini upgrade head
fi

exec "$@"
