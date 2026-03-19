#!/usr/bin/env bash
# Rebuild and restart the rbac_app Docker container.
# Safe to run repeatedly — named volume preserves DB data between restarts.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Redeploying rbac_app..."
docker compose -f "$REPO_ROOT/examples/docker-compose.yml" up --build -d
echo "rbac_app redeployed → http://localhost:8000/admin/"
