#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/deploy/napcat/compose.yml"
ENV_FILE="${PROJECT_ROOT}/.env"

usage() {
  echo "Usage: $0 {start|stop|restart|logs|status|update}" >&2
  exit 2
}

require_environment() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing ${ENV_FILE}; copy .env.example to .env first." >&2
    exit 1
  fi
  command -v docker >/dev/null || {
    echo "docker is not installed or not on PATH." >&2
    exit 1
  }
  docker compose version >/dev/null
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

prepare_runtime() {
  mkdir -p \
    "${PROJECT_ROOT}/deploy/napcat/runtime/config" \
    "${PROJECT_ROOT}/deploy/napcat/runtime/qq" \
    "${PROJECT_ROOT}/data/generated_images"
  uv run --project "${PROJECT_ROOT}" python \
    "${PROJECT_ROOT}/scripts/render_napcat_config.py"
}

require_environment
export NAPCAT_UID="${NAPCAT_UID:-$(id -u)}"
export NAPCAT_GID="${NAPCAT_GID:-$(id -g)}"

action="${1:-}"
shift || true

case "${action}" in
  start)
    prepare_runtime
    compose up -d napcat
    ;;
  stop)
    compose stop napcat
    ;;
  restart)
    prepare_runtime
    compose up -d --force-recreate napcat
    ;;
  logs)
    compose logs -f napcat "$@"
    ;;
  status)
    compose ps napcat
    ;;
  update)
    prepare_runtime
    compose pull napcat
    compose up -d --force-recreate napcat
    ;;
  *)
    usage
    ;;
esac
