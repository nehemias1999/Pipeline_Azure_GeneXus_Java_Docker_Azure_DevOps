# Contrato de asignación — REQ-02 secrets-management

## Spec a leer

- `openspec/changes/hardening-cicd-pipeline/specs/secrets-management/spec.md`
- Contexto: `openspec/changes/hardening-cicd-pipeline/proposal.md`, `design.md` (Decisions: Key Vault vs Variable Group, PAT→System.AccessToken)
- Tareas: `tasks.md` sección `2. REQ-02` (2.1, 2.2)

## PERMITIDOS (lista exacta)

- `azure-pipelines.yml` (agregar `AzureKeyVault@2` y/o `variables: - group:` linkeada; sin valores secretos)
- `templates/build.yml`, `templates/deploy.yml`, `templates/security-scan.yml` (propagar referencias `$(SecretName)`; nunca valores)
- `.ssh/known_hosts` (nuevo, fingerprint del host remoto; placeholder documentado si el fingerprint real se provee luego)
- `Pipeline_Script.yml` (SOLO redactar: reemplazar valor `ApplicationKey` hardcodeado por `$(ApplicationKey)` + aviso `legacy — no usar`; no reescribir el archivo)
- `tests/req02_secrets_test.py` (nuevo, TDD)
- Este contrato `docs/agent-contract/req-02-secrets.md`

## NUNCA

- `openspec/` (spec inmutable)
- `bat/*`, `scripts/*` (REQ-04), Artifacts/SBOM (REQ-03), gates Trivy/yamllint completos (REQ-05)
- Nuevos secretos reales, fingerprints inventados como reales (marca placeholder claramente)
- Push a `main`, merge local a `main`

## Contrato de interfaz

- Nombres de secretos (Key Vault + `issecret`): `ServerPassword`, `ApplicationKey`, `SshPrivateKey`, `SshKnownHosts`. Nombres de vault/groups por variable: `keyVaultName` (default `kv-java-app`), `vaultGroup` (default `Java_Application-Secrets` linkeada a Key Vault).
- El pipeline FALLA si un secreto requerido está vacío (paso de validación con `failOnStderr`, sin imprimir valores).
- Clonado/acceso a Azure Repos SOLO vía `System.AccessToken` o `AzureCLI@2`; prohibido `https://$(PAT)@...` o `https://%PAT%@...` en YAML/templates/scripts nuevos.
- SSH: llave desde `$(SshPrivateKey)` (secure file o Key Vault, nunca en repo), `StrictHostKeyChecking=yes` con `.ssh/known_hosts` versionado; documentar rotación en cabecera YAML.
- `Pipeline_Script.yml` legacy queda redactado (sin valor de llave) + comentario de deprecación apuntando a `azure-pipelines.yml`.

## Perfil + verificación exacta (desde raíz del worktree)

```bash
python3 -m pytest tests/req02_secrets_test.py -q || python3 tests/req02_secrets_test.py
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in ['azure-pipelines.yml']+glob.glob('templates/*.yml')]; print('YAML OK')"
grep -rn "511E367C" --exclude-dir=.git --exclude-dir=.worktrees . && exit 1 || echo "no hardcoded ApplicationKey"
grep -rn "StrictHostKeyChecking=no\|%PAT_TOKEN%\|https://.*PAT.*@" azure-pipelines.yml templates/ .ssh/ 2>/dev/null && exit 1 || echo "no insecure SSH/PAT patterns"
gitleaks detect --source . --verbose 2>&1 | tail -5 || echo "gitleaks no instalado; fallback grep OK"
```

TDD: RED = test que falla sin Key Vault wiring/redacción; GREEN = implementar; REFACTOR = deduplicar referencias a templates.

## DoD

- [ ] Key Vault task o variable-group linkeada presente; secretos solo por `$(...)`, falla si vacíos.
- [ ] Cero `ApplicationKey` hardcodeada, cero PAT en URL/CLI, cero `StrictHostKeyChecking=no` en archivos nuevos.
- [ ] `.ssh/known_hosts` existe (o placeholder documentado como tal).
- [ ] Legacy redactado con aviso de deprecación.
- [ ] Commit en `feat/req-02-secrets` + push a `origin` misma rama, `main` intacto.

## Reporte

`DONE` con archivos, salidas literales + exit codes, SHA commit. O `BLOCKED|NEEDS_CONTEXT` con gap exacto.
