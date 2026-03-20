#!/usr/bin/env bash
# Rebuild and restart the ERP example Docker container.
# Safe to run repeatedly — named volume preserves DB data between restarts.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Redeploying erp example..."
docker compose -f "$REPO_ROOT/examples/erp/docker-compose.yml" up --build -d
echo "ERP example redeployed → http://localhost:8000/admin/"
