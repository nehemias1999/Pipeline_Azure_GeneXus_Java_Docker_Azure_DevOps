# Spec Delta

## Purpose

Provee versionado semántico y trazabilidad completa desde el commit hasta el artefacto desplegado, reemplazando el commit de binarios en Git por Azure Artifacts.

## ADDED Requirements

### Requirement: Publicación versionada en Azure Artifacts con integridad

El sistema SHALL publicar cada WAR como Universal Package `java-application-dev:<semver+BuildId>` en Azure Artifacts con `SHA256` y SBOM (CycloneDX), y SHALL etiquetar el commit Git con `v<semver>`. El deploy SHALL descargar el artefacto por versión exacta, nunca por `latest` implícito.

#### Scenario: Trazabilidad commit→artefacto→deploy

- **WHEN** termina `Build` del commit `abc123`
- **THEN** existe el package `1.0.<BuildId>`, su `.sha256`, su SBOM y el tag Git correspondiente, y el log del deploy cita los tres

#### Scenario: Verificación de integridad

- **WHEN** el SHA256 descargado no coincide con el publicado
- **THEN** el pipeline falla antes de copiar al servidor

### Requirement: Prohibición de binarios en Git

El sistema SHALL NOT commitear archivos `.war` a Azure Repos; el `.gitignore` SHALL excluirlos y el pipeline SHALL fallar si detecta un WAR trackeado.

#### Scenario: WAR bloqueado en Git

- **WHEN** un PR incluye un `.war`
- **THEN** el gate de seguridad lo rechaza con mensaje de usar Artifacts
