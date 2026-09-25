# Proposal

## Why

El pipeline actual (`Pipeline_Script.yml`) está roto (`dependsOn: SetAndCreateFinalWARFile` inexistente), expone secretos (`ApplicationKey` hardcodeada, PAT en URL/CLI), usa SSH inseguro (`StrictHostKeyChecking=no`) y versiona binarios en Git sin trazabilidad. Se requiere un hardening integral CI/CD antes de operar QA/PROD.

## What Changes

- **BREAKING**: Se reemplaza `Pipeline_Script.yml` por `azure-pipelines.yml` multi-stage DEV → QA → PROD con `templates/`, parámetros y environments con approvals.
- **BREAKING**: Se elimina el push del WAR a Git Repos; los artefactos se publican en Azure Artifacts (Universal Package) con semver, SHA256 y SBOM.
- Se migran todos los secretos a Azure Key Vault + Variable Groups linkeadas; se elimina `ApplicationKey` hardcodeada y PAT en CLI/URL.
- Se reescriben `bat/*.bat` a `scripts/*.ps1` + `scripts/*.sh` idempotentes con verificación checksum, backup, healthcheck y rollback.
- Se agregan gates de seguridad: Gitleaks, Trivy (WAR/container), yamllint, permisos mínimos, `failOnStderr`, timeouts.
- Se agrega estrategia de rollback por versión (`previous-stable`) y observabilidad (retención logs, annotations).
- Se documenta con `README.md` vivo y `code-doc-standard` en scripts.

## Capabilities

### New Capabilities

- `pipeline-core-multistage`: pipeline multi-stage DEV/QA/PROD, triggers main+PR, templates reutilizables, fix del stage roto.
- `secrets-management`: secretos en Key Vault, sin hardcode, sin fuga en logs, SSH por llave.
- `artifact-versioning`: semver + Azure Artifacts + SHA256 + SBOM + tags Git, trazabilidad BuildId→artefacto→deploy.
- `hardened-deploy`: deploy remoto idempotente con checksum, backup, healthcheck y StrictHostKeyChecking=yes.
- `security-gates`: escaneos obligatorios (Gitleaks, Trivy, yamllint), approvals QA/PROD, permisos mínimos.
- `observability-docs`: retención, annotations de release, README y doc estándar de scripts.
- `rollback-strategy`: rollback a versión previa estable por parámetro.

### Modified Capabilities

_(vacío — no existen specs previas; proyecto greenfield en OpenSpec)_

## Impact

- Afecta: `Pipeline_Script.yml` (reemplazado, se conserva como legacy o se elimina), `bat/*.bat` (reemplazados por `scripts/`), nuevo `azure-pipelines.yml`, `templates/`, Azure DevOps (Key Vault, Environments DEV/QA/PROD, Artifacts feed), agente `Java_Application_agentpool`.
- Dependencias nuevas: Azure Key Vault, Azure Artifacts, Gitleaks, Trivy/Syft, yamllint.
- Sistemas: GeneXus 18U10 MSBuild, Tomcat 10.1 en Docker remoto, Azure Repos (solo código, ya no binarios).
