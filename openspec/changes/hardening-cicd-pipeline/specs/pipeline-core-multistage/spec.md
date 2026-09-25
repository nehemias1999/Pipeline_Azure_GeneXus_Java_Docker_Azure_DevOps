# Spec Delta

## Purpose

Define el pipeline multi-stage que reemplaza al Pipeline_Script.yml roto con entornos DEV, QA y PROD, plantillas reutilizables y validación en PR.

## ADDED Requirements

### Requirement: Pipeline multi-stage con environments y fix del stage roto

El sistema SHALL proveer un pipeline `azure-pipelines.yml` con stages `Build → Deploy_DEV → Deploy_QA → Deploy_PROD`, donde QA y PROD usan `environment` con approvals, y ningún stage SHALL depender de un stage inexistente.

#### Scenario: Ejecución verde en DEV

- **WHEN** se hace push a `main`
- **THEN** los stages `Build` y `Deploy_DEV` ejecutan verde y QA/PROD esperan approval

#### Scenario: Validación en PR sin deploy

- **WHEN** se abre un PR contra `main`
- **THEN** solo corre `Build` + lints y ningún deploy ejecuta

#### Scenario: Parámetros y timeouts

- **WHEN** se inspecciona cualquier job del pipeline
- **THEN** tiene `timeoutInMinutes` definido, `failOnStderr: true` en tareas shell y parámetros `environment`/`version` en lugar de valores hardcodeados

### Requirement: Plantillas reutilizables y triggers controlados

El sistema SHALL organizar pasos comunes en `templates/` (build, deploy, security-scan) y SHALL definir triggers `main` + `pr` con path filters, sin pool hardcodeado sin demands.

#### Scenario: Reuso de templates

- **WHEN** se agrega un nuevo entorno
- **THEN** se reutiliza `templates/deploy.yml` con parámetros sin duplicar YAML
