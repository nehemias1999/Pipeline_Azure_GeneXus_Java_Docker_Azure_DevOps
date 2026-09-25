# Design

## Context

Repo con `Pipeline_Script.yml` (5 stages, `dependsOn` roto a stage inexistente), `bat/*.bat` Windows-only y GeneXus 18U10 vía MSBuild en agente self-hosted `Java_Application_agentpool`. Ver `proposal.md` Why. Restricciones: agente Windows para MSBuild/GeneXus, deploy a host remoto con contenedor `tomcat` + Tomcat 10.1, Azure DevOps + Key Vault + Artifacts disponibles.

## Goals / Non-Goals

**Goals:**
- Pipeline declarativo multi-env con templates y approvals QA/PROD.
- Cero secretos en repo/logs; SSH por llave con host verificado.
- Artefactos versionados con integridad verificable y rollback por versión.

**Non-Goals:**
- Migrar GeneXus a Linux/containers de build (se mantiene MSBuild en Windows).
- Cambiar Tomcat por otro servidor o re-arquitecturar la app Java.
- IaC del host remoto (fuera de alcance; solo deploy).

## Decisions

- **Nuevo `azure-pipelines.yml` + `templates/` (build.yml, deploy.yml, security-scan.yml) sobre parchear `Pipeline_Script.yml`**: el archivo actual tiene stage fantasma y variables hardcodeadas; templates permiten reuso por entorno. Alternativa (parche mínimo) descartada por deuda acumulada.
- **Key Vault + Variable Group linkeada vs. Variable Group con secretos manuales**: Key Vault da rotación, auditoría y RBAC; Variables con `issecret` solas no auditan acceso. PAT se elimina: se usa `System.AccessToken` + `AzureCLI@2`.
- **Azure Artifacts Universal Package + SHA256 + SBOM (Syft/CycloneDX) vs. seguir en Git Repos**: Git no es store de binarios (bloat, sin integridad); Artifacts da inmutabilidad por versión y trazabilidad. `Pipeline_Script.yml` + `pushToAzureRepository.bat` quedan legacy.
- **Scripts `scripts/*.ps1` + `*.sh` idempotentes vs. mantener `.bat`**: `.bat` no tiene `set -euo pipefail`, ni checksum, ni healthcheck; PS1/SH permiten `fail-fast`, `sha256sum`, `curl --fail` y backup/rollback. Se conserva compatibilidad Windows (PS1) para el agente y SH para el host.
- **Trivy + Gitleaks + yamllint como gates bloqueantes vs. solo advisory**: sin bloqueo, los scans se ignoran; se configuran como `failed` en HIGH/CRITICAL. SARIF se publica como artefacto.
- **Deploy con backup + healthcheck + rollback automático vs. deploy directo**: `shutdown.sh/pkill -9` actual deja ventanas caídas; backup `*.bak-<version>` + `curl --fail --max-time` + restore reduce MTTR.

## Risks / Trade-offs

- [Key Vault sin acceso desde el agente] → Mitigación: service connection con Managed Identity + pre-check `AzureKeyVault@2`; documentar setup en README.
- [GeneXus/MSBuild no disponible en QA/PROD agents] → Mitigación: Build una sola vez en DEV, promover el mismo artefacto inmutable (no rebuild por entorno).
- [Fingerprint SSH cambia tras reprovisionar host] → Mitigación: `known_hosts` versionado + runbook de rotación; el fallo es explícito y auditable.
- [Trivy HIGH falsos positivos bloquean] → Mitigación: allowlist versionada `trivy-ignore.yml` con expiración y aprobación en PR.
- [Agente Windows sin `yamllint`/`trivy`] → Mitigación: usar imágenes/container jobs o tasks de marketplace con fallback a script; fijar versiones.

## Migration Plan

1. Crear Key Vault + feed Artifacts + Environments QA/PROD (manual, una vez; documentado).
2. Mergear `azure-pipelines.yml` + templates + scripts en `main` vía PRs por REQ; `Pipeline_Script.yml` y `bat/` se marcan `legacy/` y luego se eliminan.
3. Rotar `ApplicationKey`, `ServerPassword`, PAT y llave SSH (revocar los expuestos).
4. Primer run en DEV con artefacto `1.0.<BuildId>`; promover a QA/PROD con approvals.
5. Rollback: lanzar job `Rollback` con versión previa; restore automático si healthcheck falla.

## Open Questions

- Nombre final del feed Artifacts y del Key Vault (usar defaults `java-app-artifacts` / `kv-java-app-<env>` si no se indica).
- URL del healthcheck de la app (default `http://<host>:8080/<app>/health` o root `200`).
