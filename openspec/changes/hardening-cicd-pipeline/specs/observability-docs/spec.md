# Spec Delta

## Purpose

Asegura visibilidad operativa del pipeline y mantiene la documentación viva y verificable contra el repo real.

## ADDED Requirements

### Requirement: Observabilidad del pipeline

El sistema SHALL retener logs por 30 días, publicar el resumen de release (versión, commit, artefacto, SHA, environment, aprobador) como artefacto y SHALL anotar cada deploy con timestamp e identidad del aprobador.

#### Scenario: Auditoría de un deploy

- **WHEN** se consulta el deploy `PROD 1.0.42`
- **THEN** se recupera versión, commit, SHA256, quién aprobó y cuándo, desde artefactos retenidos

### Requirement: Documentación viva estándar

El sistema SHALL mantener `README.md` actualizado (descripción, arquitectura, setup, comandos de verificación, spec link) según `readme-standard` y SHALL documentar cada script con `code-doc-standard`. El reviewer SHALL fallar si hay drift entre README y repo real.

#### Scenario: README refleja el pipeline real

- **WHEN** se agrega un environment o cambia un comando de verificación
- **THEN** el README se actualiza en el mismo cambio o el review marca `FAIL`
