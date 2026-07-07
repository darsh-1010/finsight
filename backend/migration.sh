#!/bin/bash
set -e

MAX_RETRIES=5
RETRY_DELAY=5

echo "Running database migrations..."

for i in $(seq 1 $MAX_RETRIES); do
  if alembic upgrade head; then
    echo "Migrations completed successfully."
    exit 0
  else
    if [ "$i" -eq "$MAX_RETRIES" ]; then
      echo "ERROR: Migrations failed after $MAX_RETRIES attempts."
      exit 1
    fi

    echo "Migration attempt $i/$MAX_RETRIES failed. Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
  fi
done