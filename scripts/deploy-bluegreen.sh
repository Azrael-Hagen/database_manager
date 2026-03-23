#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-deploy}"
COLOR="${2:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.bluegreen.yml}"
ACTIVE_FILE="${ACTIVE_FILE:-deploy/active-upstream.conf}"

if [[ ! -f "$ACTIVE_FILE" ]]; then
  mkdir -p "$(dirname "$ACTIVE_FILE")"
  echo "proxy_pass http://backend_blue:8000;" > "$ACTIVE_FILE"
fi

active_color() {
  if grep -q "backend_green" "$ACTIVE_FILE"; then
    echo "green"
  else
    echo "blue"
  fi
}

set_active_color() {
  local color="$1"
  if [[ "$color" == "blue" ]]; then
    echo "proxy_pass http://backend_blue:8000;" > "$ACTIVE_FILE"
  else
    echo "proxy_pass http://backend_green:8000;" > "$ACTIVE_FILE"
  fi
  docker compose -f "$COMPOSE_FILE" exec gateway nginx -s reload >/dev/null
}

wait_healthy() {
  local color="$1"
  local port="18000"
  if [[ "$color" == "green" ]]; then
    port="18001"
  fi

  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

print_status() {
  echo "Active color: $(active_color)"
  docker compose -f "$COMPOSE_FILE" ps
}

case "$ACTION" in
  status)
    print_status
    ;;

  switch)
    if [[ -z "$COLOR" || ("$COLOR" != "blue" && "$COLOR" != "green") ]]; then
      echo "Usage: ./scripts/deploy-bluegreen.sh switch [blue|green]"
      exit 1
    fi
    set_active_color "$COLOR"
    echo "Switch completado a $COLOR"
    print_status
    ;;

  deploy)
    docker compose -f "$COMPOSE_FILE" up -d mariadb backend_blue backend_green gateway

    ACTIVE="$(active_color)"
    if [[ "$ACTIVE" == "blue" ]]; then
      TARGET="green"
      OLD="backend_blue"
    else
      TARGET="blue"
      OLD="backend_green"
    fi

    echo "Color activo: $ACTIVE"
    echo "Desplegando color objetivo: $TARGET"

    docker compose -f "$COMPOSE_FILE" up -d --build "backend_${TARGET}"

    if ! wait_healthy "$TARGET"; then
      echo "ERROR: backend_${TARGET} no pasó healthcheck"
      exit 1
    fi

    set_active_color "$TARGET"
    docker compose -f "$COMPOSE_FILE" stop "$OLD" >/dev/null || true

    echo "Deploy sin downtime completado. Activo: $TARGET"
    print_status
    ;;

  *)
    echo "Uso: ./scripts/deploy-bluegreen.sh [deploy|status|switch] [blue|green]"
    exit 1
    ;;
esac
