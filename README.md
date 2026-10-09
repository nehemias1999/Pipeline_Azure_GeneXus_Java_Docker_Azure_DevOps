# Pipeline Azure DevOps — GeneXus Java + Docker + Tomcat

CI/CD multi-stage (Build, Deploy_DEV, Deploy_QA, Deploy_PROD) que compila la app Java generada por GeneXus, publica el WAR versionado con SHA256 y lo despliega en Tomcat/Docker con gates de seguridad bloqueantes.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [API / Configuration](#api--configuration)
- [Contributing](#contributing)
- [License](#license)

## Background

Reemplaza al pipeline legacy (`Pipeline_Script.yml`, scripts `bat/`) que tenia stages fantasma y secretos hardcodeados: ahora el WAR se publica una sola vez como Universal Package inmutable y cada entorno despliega la version exacta con SHA verificado, backup y healthcheck con rollback.

### Tecnologias

Azure DevOps Pipelines, GeneXus 18 (Java) + MSBuild, Java / Apache Tomcat, Docker, Azure Artifacts (Universal Packages), Azure Key Vault, Gitleaks + Trivy + yamllint (gates), SSH endurecido.

### Arquitectura / Flujo

`azure-pipelines.yml` (stages Build, Deploy_DEV auto en main, Deploy_QA/PROD con environment + approval) → `templates/build.yml` (compila y publica `java-application-dev:<version>` + `.sha256` + SBOM + tag `v<version>`) → `templates/security-scan.yml` (Gitleaks, Trivy fs/WAR con SARIF, yamllint) → `templates/deploy.yml` (descarga version exacta, verifica SHA, `scripts/deploy-docker-tomcat.sh` o `scripts/deploy-docker-tomcat.ps1` con backup/healthcheck/rollback). Build publica `pipeline-metadata` y `release-summary` (version, commit, artefacto, SHA256, environment, aprobador; retencion 30 dias); cada deploy se anota con timestamp + aprobador (`$(Build.RequestedFor)` en runtime).

Spec fuente de verdad: `openspec/changes/hardening-cicd-pipeline/specs/observability-docs/spec.md`.

## Install

Prerrequisitos: agente `Java_Application_agentpool` con demands `msbuild` + `GeneXus_18U10`; feed `java-app-artifacts`; Key Vault `kv-java-app` con service connection `azure-keyvault-service-connection`; variable group `Java_Application-Secrets`; variable `healthUrl_<ENV>` por entorno.

```bash
git clone <repo> && cd <repo>
python3 -m unittest discover -s tests -p "*_test.py"
```

## Usage

Push a `main` corre Build + Deploy_DEV; QA/PROD avanzan tras approval del environment en Azure DevOps. Run manual con parametros `environment` (DEV/QA/PROD) y `version` (default `1.0.$(Build.BuildId)`). Auditoria de un deploy (ej. `PROD 1.0.42`): descargar el artefacto `release-summary` del build y leer `release-summary.json` (version, commit, sha256, aprobador, timestamp).

## API / Configuration

| Variable | Requerida | Default | Formato |
|---|---|---|---|
| `appVersion` | no | `1.0.$(Build.BuildId)` | `1.0.<BuildId>` |
| `artifactFeed` | no | `java-app-artifacts` | nombre de feed |
| `keyVaultName` / `vaultGroup` | si | `kv-java-app` / `Java_Application-Secrets` | nombres Azure |
| `ServerPassword`, `ApplicationKey`, `SshPrivateKey`, `SshKnownHosts` | si (via Key Vault) | — | nunca en repo |
| `healthUrl_<ENV>` | no | `http://localhost:8080/` | URL http(s) |
| `releaseRetentionDays` | no | `30` | dias (retencion en Project Settings > Pipelines > Retention) |

## Contributing

Entorno local: `python3` + `pyyaml`. Verificaciones (todas en verde antes de PR):

```bash
python3 -m unittest discover -s tests -p "*_test.py"
yamllint azure-pipelines.yml templates/deploy.yml
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['azure-pipelines.yml','templates/deploy.yml']]"
openspec validate --specs
```

Commits: Conventional Commits (`feat(req-06): ...`). Nunca modificar `openspec/` ni tests de otros requisitos.

## License

MIT.
