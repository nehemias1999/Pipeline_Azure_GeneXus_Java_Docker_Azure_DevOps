# Contrato de asignación — REQ-01 pipeline-core-multistage

## Spec a leer

- `openspec/changes/hardening-cicd-pipeline/specs/pipeline-core-multistage/spec.md`
- Contexto: `openspec/changes/hardening-cicd-pipeline/proposal.md`, `openspec/changes/hardening-cicd-pipeline/design.md` (secciones Context, Decisions, Migration Plan)
- Tareas: `openspec/changes/hardening-cicd-pipeline/tasks.md` sección `1. REQ-01` (1.1, 1.2, 1.3)

## PERMITIDOS (lista exacta)

- `azure-pipelines.yml` (nuevo)
- `templates/build.yml` (nuevo)
- `templates/deploy.yml` (nuevo)
- `templates/security-scan.yml` (nuevo, stub mínimo que REQ-05 completará; no implementar scans completos aquí)
- `.gitignore` (solo si falta entrada `*.war`, ya existe)

## NUNCA

- `openspec/` (spec inmutable)
- `Pipeline_Script.yml`, `bat/*`, `scripts/*` (de REQ-02..04)
- Tests o archivos de otros REQs
- Push a `main`, merge local a `main`

## Contrato de interfaz

- `azure-pipelines.yml` expone parámetros `environment` (`DEV/QA/PROD`) y `version` (`1.0.$(BuildId)` default); stages: `Build` (siempre) → `Deploy_DEV` (auto, `main`) → `Deploy_QA`/`Deploy_PROD` (`environment: QA/PROD`, `condition: succeeded()`, esperan approval).
- `templates/deploy.yml` recibe `parameters: { environment: string, version: string, artifactFeed: string }` y despliega el artefacto exacto (descarga real la implementa REQ-03/04; aquí basta con validar parámetros y fallar si vacíos).
- Ningún stage depende de stage inexistente; `Build` publica `pipeline-metadata` (versión, commit) como artefacto mínimo.
- Triggers: `trigger: branches: [main]` + `pr: branches: [main]`; `pool` con `demands` documentadas para GeneXus/MSBuild.

## Perfil de proyecto + verificación exacta

Perfil: **Pipeline/CI-CD**. Comandos (desde raíz del worktree):

```bash
yamllint azure-pipelines.yml templates/*.yml
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in ['azure-pipelines.yml']+glob.glob('templates/*.yml')]; print('YAML OK')"
grep -rn "SetAndCreateFinalWARFile" azure-pipelines.yml templates/ && exit 1 || echo "no dangling dependsOn"
grep -rn "511E367C\|10.200.200.200" azure-pipelines.yml templates/ && exit 1 || echo "no hardcoded secrets/IP"
```

TDD: RED = crear un `tests/req01_pipeline_test.py` (o script de validación) que falle sin los archivos; GREEN = implementar YAML hasta pasar; REFACTOR = extraer duplicación a templates.

## DoD verificable

- [ ] `azure-pipelines.yml` + 3 templates existen y parsean.
- [ ] `yamllint` limpio, sin `dependsOn` fantasma, sin secretos/IP hardcodeados.
- [ ] `Build` corre en PR sin deploys; QA/PROD tienen `environment` con approval.
- [ ] Todos los jobs tienen `timeoutInMinutes` y `failOnStderr: true` donde aplique.
- [ ] Commit en `feat/req-01-pipeline-core` dentro del worktree, push a `origin` misma rama, sin tocar `main`.

## Formato de reporte

Responde `DONE` con: archivos creados, salida literal de los 4 comandos de verificación (exit codes), y SHA del commit. O `BLOCKED|NEEDS_CONTEXT` con el gap exacto.
