#!/bin/bash

# Weaviate Nuclear Reset Script
# This script forcefully resolves "strategy mismatch" panics by purging Docker volumes
# and re-initializing the database with a harmonized schema.

set -e

echo "--- 1. STOPPING SERVICES AND PURGING VOLUMES ---"
docker compose down -v

echo "--- 2. STARTING WEAVIATE AND REDIS ---"
# We start weaviate and redis first to ensure they are ready for initialization
docker compose up -d weaviate redis

echo "--- 3. WAITING FOR WEAVIATE TO BE READY ---"
# Give weaviate some time to boot up completely
max_retries=30
count=0
while ! curl -s http://localhost:8080/v1/.well-known/ready > /dev/null; do
    ((count++))
    if [ $count -gt $max_retries ]; then
        echo "Error: Weaviate failed to start in time."
        exit 1
    fi
    echo "Waiting for Weaviate... ($count/$max_retries)"
    sleep 2
done

echo "--- 4. INITIALIZING HARMONIZED SCHEMA ---"
# Run the python refresh script to create the collection with the new stable schema
PYTHONPATH=. python3 src/scripts/weaviate_refresh.py

echo "--- 5. STARTING APPLICATION SERVICES ---"
docker compose up -d app scraper

echo "--- NUCLEAR RESET COMPLETE ---"
echo "The Weaviate database is now clean and using the harmonized schema."
echo "You can now safely re-ingest your documents."
