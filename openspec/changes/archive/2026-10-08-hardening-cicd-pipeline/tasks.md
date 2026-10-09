# Tasks

## 1. REQ-01 pipeline-core-multistage

- [ ] 1.1 Crear `azure-pipelines.yml` multi-stage (Build, DEV, QA, PROD) sin dependsOn roto y verificar con `yamllint azure-pipelines.yml` y `python3 -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"`
- [ ] 1.2 Crear `templates/build.yml`, `templates/deploy.yml`, `templates/security-scan.yml` parametrizados y verificar que `azure-pipelines.yml` los referencia y el parse YAML pasa
- [ ] 1.3 Configurar triggers `main` + `pr`, `timeoutInMinutes`, `failOnStderr: true` y `permissions: contents: read`, verificar por inspección + `yamllint templates/*.yml`

## 2. REQ-02 secrets-management

- [ ] 2.1 Migrar `ApplicationKey`, `ServerPassword`, SSH key a Key Vault via `AzureKeyVault@2` + Variable Groups y verificar con `grep -r "511E367C" --exclude-dir=.git --exclude-dir=openspec .` vacío y `gitleaks detect --source . --verbose` limpio
- [ ] 2.2 Eliminar PAT de URL/CLI (usar `System.AccessToken`/`AzureCLI@2`) y verificar que `grep -rn "PATToken\|_git.*\$(" azure-pipelines.yml templates/ scripts/ | grep -v System.AccessToken` no expone token

## 3. REQ-03 artifact-versioning

- [ ] 3.1 Publicar WAR en Azure Artifacts como Universal Package `1.0.$(BuildId)` con `.sha256` + SBOM CycloneDX y verificar descarga + `sha256sum -c` en job de promoción
- [ ] 3.2 Agregar tag Git `v1.0.<BuildId>`, `.gitignore` para `*.war` y gate que falla si hay WAR trackeado, verificar con `git check-ignore` y `git ls-files "*.war"` vacío

## 4. REQ-04 hardened-deploy

- [ ] 4.1 Crear `scripts/deploy-docker-tomcat.ps1` y `.sh` idempotentes (checksum, backup `*.bak-<version>`, healthcheck `curl --fail`, restore) con cabecera `code-doc-standard` y verificar con `pwsh -NoProfile -Command "Get-Content scripts/deploy-docker-tomcat.ps1"` + `bash -n scripts/deploy-docker-tomcat.sh`
- [ ] 4.2 Endurecer SSH (`StrictHostKeyChecking=yes`, `known_hosts` versionado, `BatchMode=yes`) y verificar que `grep -rn "StrictHostKeyChecking=no" azure-pipelines.yml templates/ scripts/` está vacío

## 5. REQ-05 security-gates

- [ ] 5.1 Agregar gates Gitleaks + Trivy (fs+WAR, SARIF) + yamllint bloqueantes en Build/PR y verificar que un secreto fixture y `trivy --severity HIGH,CRITICAL` fallan el build en prueba local
- [ ] 5.2 Configurar `environment: QA/PROD` con approvals y verificar por inspección YAML que `Deploy_QA/PROD` tienen `environment` + `condition: succeeded()`

## 6. REQ-06 observability-docs

- [ ] 6.1 Publicar resumen de release (versión, commit, SHA, aprobador) como artefacto con retención 30 días y verificar que el log cita versión+SHA+tag
- [ ] 6.2 Actualizar `README.md` con `readme-standard` y doc `code-doc-standard` en scripts, verificar anti-drift contra repo real (nombres de archivos, comandos)

## 7. REQ-07 rollback-strategy

- [ ] 7.1 Crear job manual `Rollback` parametrizado (`version`, default `previous-stable`) que despliega artefacto exacto con healthcheck y verificar en dry-run que versión inexistente falla listando disponibles

## 8. Cierre

- [ ] 8.1 Ejecutar `openspec validate --strict` limpio y `git status` con solo archivos del change + implementación del REQ en curso
