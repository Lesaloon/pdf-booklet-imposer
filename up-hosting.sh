#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

require_env() {
    if [ ! -f .env ]; then
        printf '%s\n' 'Missing .env. Copy .env.example to .env and configure the Cloudflare tunnel token before starting.' >&2
        exit 1
    fi
}

require_env
git pull --ff-only
require_env
docker compose --env-file .env --profile hosting config --quiet
docker compose --env-file .env --profile hosting build
docker compose --env-file .env --profile hosting down
docker compose --env-file .env --profile hosting up -d --wait --wait-timeout 120
