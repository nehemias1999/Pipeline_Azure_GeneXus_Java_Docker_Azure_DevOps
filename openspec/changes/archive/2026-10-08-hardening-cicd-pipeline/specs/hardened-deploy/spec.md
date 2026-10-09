# Spec Delta

## Purpose

Hace el despliegue remoto a Docker/Tomcat idempotente, verificable y seguro, reemplazando los scripts .bat frágiles por scripts documentados con healthcheck.

## ADDED Requirements

### Requirement: Deploy idempotente con verificación y backup

El sistema SHALL copiar el WAR verificado por SHA256 al servidor, respaldar la versión previa (`*.bak-<version>`), desplegar en el contenedor `tomcat` y SHALL verificar `startup.sh` + healthcheck HTTP antes de declarar éxito. Si el healthcheck falla, SHALL restaurar el backup automáticamente.

#### Scenario: Deploy verde con healthcheck

- **WHEN** se despliega la versión `1.0.42` en DEV
- **THEN** Tomcat responde `200` en el endpoint de salud dentro del timeout y el backup previo existe

#### Scenario: Healthcheck fallido restaura backup

- **WHEN** Tomcat no responde `200` tras el deploy
- **THEN** se restaura el WAR anterior y el stage marca `failed` con el log del healthcheck

### Requirement: Scripts portables y documentados

El sistema SHALL proveer `scripts/deploy-docker-tomcat.ps1` y `.sh` con cabecera `code-doc-standard` (propósito, uso, exit codes), parámetros validados y manejo de errores explícito (`set -euo pipefail` / `$ErrorActionPreference='Stop'`), sin `pkill -9` incondicional.

#### Scenario: Parámetros inválidos fallan rápido

- **WHEN** se invoca el script sin `WAR_PATH` o versión
- **THEN** imprime uso y sale con código `1` sin tocar el servidor
