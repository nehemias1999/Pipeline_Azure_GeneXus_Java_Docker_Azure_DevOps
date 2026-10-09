# Spec Delta

## Purpose

Permite revertir un despliegue defectuoso a la última versión estable conocida mediante un job manual parametrizado por versión.

## ADDED Requirements

### Requirement: Rollback parametrizado a previous-stable

El sistema SHALL exponer un job/stage manual `Rollback` que recibe `version` (default: `previous-stable`), descarga ese artefacto exacto de Artifacts, lo despliega con el mismo flujo endurecido y SHALL verificar healthcheck antes de cerrar.

#### Scenario: Rollback exitoso

- **WHEN** PROD `1.0.43` falla y se lanza `Rollback` con `1.0.42`
- **THEN** PROD vuelve a `1.0.42` verificado con healthcheck `200` y queda anotado como rollback

#### Scenario: Versión inexistente falla rápido

- **WHEN** se pide rollback a una versión no publicada
- **THEN** el job falla antes de tocar el servidor listando versiones disponibles
