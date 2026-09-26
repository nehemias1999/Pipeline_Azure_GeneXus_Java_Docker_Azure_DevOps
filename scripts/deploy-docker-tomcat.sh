#!/usr/bin/env bash
# ==============================================================================
# Description: Despliega un WAR verificado por SHA256 en Tomcat dentro de un
#   contenedor Docker remoto via SSH endurecido. Flujo idempotente: re-chequea
#   el SHA local, copia con scp, respalda la version previa (*.bak-<version>),
#   apaga Tomcat graceful (pkill solo como fallback tras timeout, logueado),
#   enciende y verifica healthcheck HTTP con reintentos; ante fallo restaura
#   el backup y sale 1. Reemplaza los .bat legacy (ver bat/README.legacy.md).
# Author: nehemias1999
# Usage: ./deploy-docker-tomcat.sh --war-path <app.war> --version <1.0.42>
#   --ssh-target <usuario@host> [--container-name tomcat]
#   [--webapps-path /usr/local/tomcat/webapps] [--health-url <url>]
#   [--timeout-sec 120]
# Env Vars: ninguna requerida (usa la llave del agente SSH o ~/.ssh/config).
#   HEALTH_URL_<ENV> no aplica aqui: el
#   caller (templates/deploy.yml) resuelve healthUrl_<ENV> y lo pasa como
#   --health-url.
# Dependencies: bash, ssh, scp, sha256sum, curl (agente); docker, pgrep,
#   pkill (host remoto, pkill solo fallback); Tomcat con shutdown.sh/startup.sh
# Output / Exit codes: STDOUT = progreso (sin secretos); STDERR = errores y
#   validacion. 0 = deploy + healthcheck OK; 1 = params invalidos, WAR/SHA
#   invalidos, copia, ciclo Tomcat, healthcheck (con restore) o SSH fallidos.
#   Default --health-url: http://localhost:8080/ (curleado EN el servidor).
# ==============================================================================
set -euo pipefail

WAR_PATH=""
VERSION=""
SSH_TARGET=""
CONTAINER_NAME="tomcat"
WEBAPPS_PATH="/usr/local/tomcat/webapps"
HEALTH_URL=""
TIMEOUT_SEC="120"

SSH_OPTS=(-o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=10)

# usage: imprime ayuda a STDOUT. $1 = exit code con el que sale el caller.
usage() {
  cat <<'EOF'
Usage: deploy-docker-tomcat.sh --war-path <app.war> --version <x.y.z> --ssh-target <usuario@host> [opciones]

Despliega un WAR en Tomcat/Docker remoto con backup y healthcheck.

Opciones:
  --war-path <ruta>       WAR a desplegar (requerido, debe existir)
  --version <ver>         Version exacta, p.ej. 1.0.42 (requerido)
  --ssh-target <u@h>      Destino SSH, p.ej. deploy@tomcat-dev (requerido)
  --container-name <n>    Contenedor Docker (default: tomcat)
  --webapps-path <ruta>   webapps dentro del contenedor
                          (default: /usr/local/tomcat/webapps)
  --health-url <url>      Endpoint de salud (default: http://localhost:8080/)
  --timeout-sec <n>       Timeout graceful + healthcheck (default: 120)
  -h, --help              Muestra esta ayuda y sale 0
EOF
}

if [ "$#" -eq 0 ]; then
  echo "error: faltan parametros requeridos" >&2
  usage >&2
  exit 1
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --war-path) WAR_PATH="${2:-}"; shift 2 ;;
    --version) VERSION="${2:-}"; shift 2 ;;
    --ssh-target) SSH_TARGET="${2:-}"; shift 2 ;;
    --container-name) CONTAINER_NAME="${2:-}"; shift 2 ;;
    --webapps-path) WEBAPPS_PATH="${2:-}"; shift 2 ;;
    --health-url) HEALTH_URL="${2:-}"; shift 2 ;;
    --timeout-sec) TIMEOUT_SEC="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: opcion desconocida: $1" >&2; usage >&2; exit 1 ;;
  esac
done

missing=0
if [ -z "$WAR_PATH" ]; then echo "error: --war-path requerido" >&2; missing=1; fi
if [ -z "$VERSION" ]; then echo "error: --version requerido" >&2; missing=1; fi
if [ -z "$SSH_TARGET" ]; then echo "error: --ssh-target requerido" >&2; missing=1; fi
if [ "$missing" -ne 0 ]; then usage >&2; exit 1; fi
if [ -z "$HEALTH_URL" ]; then HEALTH_URL="http://localhost:8080/"; fi

# Fail-fast local: el WAR debe existir ANTES de tocar el servidor.
if [ ! -f "$WAR_PATH" ]; then
  echo "error: WAR no encontrado: $WAR_PATH" >&2
  exit 1
fi

# Re-check SHA256 local si viaja el .sha256 hermano (REQ-03 lo publica).
if [ -f "${WAR_PATH}.sha256" ]; then
  sha256sum --check "${WAR_PATH}.sha256"
  echo "SHA256 local OK: $WAR_PATH"
fi

APP_NAME="$(basename "$WAR_PATH" .war)"
REMOTE_TMP="/tmp/${APP_NAME}-${VERSION}.war"

echo "Copiando $WAR_PATH a ${SSH_TARGET}:${REMOTE_TMP}"
scp "${SSH_OPTS[@]}" "$WAR_PATH" "${SSH_TARGET}:${REMOTE_TMP}"

echo "Desplegando version $VERSION en contenedor $CONTAINER_NAME"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" \
  "CONTAINER='$CONTAINER_NAME'" \
  "WEBAPPS='$WEBAPPS_PATH'" \
  "APP='$APP_NAME'" \
  "WAR='$REMOTE_TMP'" \
  "VERSION='$VERSION'" \
  "HEALTH='$HEALTH_URL'" \
  "GRACE='$TIMEOUT_SEC'" \
  'bash -s' <<'REMOTE_EOF'
set -euo pipefail
TARGET="$WEBAPPS/$APP.war"
PREV="$WEBAPPS/$APP.war.bak-$VERSION"

# Backup de la version previa, idempotente (no pisa un backup igual).
if [ -f "$TARGET" ]; then
  cp --force "$TARGET" "$PREV"
  echo "backup previo en $PREV"
fi

docker cp "$WAR" "$CONTAINER:$TARGET"
rm --force "$WAR"
echo "WAR copiado al contenedor $CONTAINER"

# Apagado graceful; espera hasta GRACE segundos.
docker exec "$CONTAINER" "$WEBAPPS/../bin/shutdown.sh" || true
waited=0
while docker exec "$CONTAINER" pgrep -f catalina >/dev/null 2>&1; do
  if [ "$waited" -ge "$GRACE" ]; then break; fi
  sleep 5
  waited=$((waited + 5))
done

# Fallback tras timeout: pkill solo si el proceso persiste, logueado.
if docker exec "$CONTAINER" pgrep -f catalina >/dev/null 2>&1; then
  echo "WARN: shutdown graceful excedio el timeout, fallback pkill (logueado)" >&2 # fallback tras timeout
  docker exec "$CONTAINER" pkill -9 -f catalina || true # fallback tras timeout
  sleep 5
fi

docker exec "$CONTAINER" "$WEBAPPS/../bin/startup.sh"

# Healthcheck con reintentos: curl --fail dentro del timeout total.
attempts=$(( (GRACE + 9) / 10 ))
ok=0
for ((i = 1; i <= attempts; i++)); do
  if docker exec "$CONTAINER" curl --fail --silent --max-time 10 "$HEALTH" >/dev/null 2>&1; then
    ok=1
    echo "healthcheck OK (intento $i/$attempts): $HEALTH"
    break
  fi
  echo "healthcheck intento $i/$attempts sin 200, reintentando..."
  sleep 10
done

# Restore: ante fallo de salud se vuelve al backup y se marca failed.
if [ "$ok" -ne 1 ]; then
  echo "ERROR: healthcheck fallo tras $attempts intentos, restaurando backup" >&2
  if [ -f "$PREV" ]; then
    docker cp "$PREV" "$CONTAINER:$TARGET"
    docker exec "$CONTAINER" "$WEBAPPS/../bin/startup.sh" || true
    echo "backup restaurado desde $PREV" # restore del backup previo
  fi
  exit 1
fi
REMOTE_EOF

echo "Deploy $VERSION OK con healthcheck en $HEALTH_URL"
