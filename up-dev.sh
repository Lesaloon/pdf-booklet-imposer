#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

require_env() {
    if [ ! -f .env ]; then
        printf '%s\n' 'Missing .env. Copy .env.example to .env and configure it before starting.' >&2
        exit 1
    fi
}

require_env
git pull --ff-only
require_env
docker compose --env-file .env config --quiet
docker compose --env-file .env build
# Include the hosting profile when stopping so switching modes stops the tunnel.
docker compose --env-file .env --profile hosting down
docker compose --env-file .env up -d --wait --wait-timeout 120
