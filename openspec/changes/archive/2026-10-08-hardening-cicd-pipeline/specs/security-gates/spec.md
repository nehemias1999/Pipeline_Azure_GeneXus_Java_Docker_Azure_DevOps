# Spec Delta

## Purpose

Bloquea vulnerabilidades y mala configuración antes del despliegue mediante escaneos obligatorios y aprobaciones humanas en QA y PROD.

## ADDED Requirements

### Requirement: Gates de escaneo bloqueantes en Build

El sistema SHALL ejecutar en cada Build/PR: `Gitleaks` (secretos), `Trivy` (filesystem + WAR) y `yamllint` (pipeline/templates), y SHALL marcar el build como `failed` ante hallazgo `HIGH/CRITICAL` o secreto detectado.

#### Scenario: Secreto bloquea el PR

- **WHEN** un PR introduce una cadena con entropía de secreto
- **THEN** Gitleaks falla el gate y lista el archivo sin exponer el valor

#### Scenario: Vulnerabilidad crítica bloquea

- **WHEN** Trivy reporta `CRITICAL` en el WAR
- **THEN** el pipeline falla y publica el reporte SARIF como artefacto

### Requirement: Approvals y permisos mínimos

El sistema SHALL requerir approval manual en los environments `QA` y `PROD`, y SHALL usar `permissions: contents: read` + `System.AccessToken` de alcance mínimo; ningún job SHALL usar credenciales de amplio alcance.

#### Scenario: PROD espera aprobación

- **WHEN** DEV y QA están verdes
- **THEN** `Deploy_PROD` queda en `waiting` hasta el approval registrado con identidad y timestamp
