# Contrato de asignación — REQ-03 artifact-versioning

## Spec a leer

- `openspec/changes/hardening-cicd-pipeline/specs/artifact-versioning/spec.md`
- Contexto: `proposal.md`, `design.md` (Decisions: Artifacts Universal + SHA256 + SBOM vs Git)
- Tareas: `tasks.md` sección `3. REQ-03` (3.1, 3.2)

## PERMITIDOS (lista exacta)

- `templates/build.yml` (publicar WAR en Artifacts + `.sha256` + SBOM CycloneDX; tag Git `v<version>`)
- `templates/deploy.yml` (descargar versión exacta + `sha256sum -c`; falla si mismatch)
- `azure-pipelines.yml` (wiring `artifactFeed`/`appVersion`, paso de tag; sin secretos)
- `.gitignore` (verificar `*.war`; agregar si falta)
- `tests/req03_artifacts_test.py` (nuevo, TDD)
- Este contrato `docs/agent-contract/req-03-artifacts.md`

## NUNCA

- `openspec/`, `bat/*`, `scripts/*` (REQ-04), `Pipeline_Script.yml` (legacy ya redactado), Key Vault wiring (REQ-02 hecho), scans (REQ-05)
- WAR reales commiteados, tags inventados sin versión, SBOM falsos (si syft no está, generar manifest documentado como placeholder)
- Push a `main`, merge local a `main`

## Interfaz

- Versión: `1.0.$(Build.BuildId)` via `$(appVersion)` / `${{ parameters.version }}`; package `java-application-dev:<version>` en feed `$(artifactFeed)` (default `java-app-artifacts`).
- Build publica: WAR + `<war>.sha256` + `sbom.cyclonedx.json` como Universal Package; tag Git `v<version>` (push con `System.AccessToken`, `persistCredentials: true` en checkout).
- Deploy descarga por versión EXACTA y verifica SHA antes de cualquier copia; `latest` implícito prohibido.
- `.gitignore` excluye `*.war`; el pipeline falla si `git ls-files "*.war"` no está vacío (gate en build.yml).

## Verificación exacta (raíz del worktree)

```bash
python3 -m pytest tests/req03_artifacts_test.py -q || python3 tests/req03_artifacts_test.py
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in ['azure-pipelines.yml']+glob.glob('templates/*.yml')]; print('YAML OK')"
git ls-files "*.war" | grep . && exit 1 || echo "no WAR trackeados"
grep -rn "latest" templates/deploy.yml | grep -iv "latest-" | grep -i "version.*latest\|latest.*version" && exit 1 || echo "sin latest implicito"
```

TDD: RED = test falla sin publish/verify/tag; GREEN = implementar; REFACTOR = deduplicar.

## DoD

- [ ] Publish a Artifacts con SHA256 + SBOM + tag `v*` en build.yml.
- [ ] Deploy verifica SHA de versión exacta, falla en mismatch.
- [ ] Sin WAR en Git, sin `latest` implícito, YAML parse OK.
- [ ] Commit en `feat/req-03-artifacts` + push origin misma rama, `main` intacto.

## Reporte

`DONE` con archivos, salidas + exit codes, SHA. O `BLOCKED|NEEDS_CONTEXT` con gap exacto.
