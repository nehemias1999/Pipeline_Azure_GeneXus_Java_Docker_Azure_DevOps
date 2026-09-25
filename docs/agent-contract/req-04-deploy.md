# Contrato de asignación — REQ-04 hardened-deploy

## Spec a leer

- `openspec/changes/hardening-cicd-pipeline/specs/hardened-deploy/spec.md`
- Contexto: `design.md` (Decisions: PS1+SH idempotentes vs .bat; backup+healthcheck+restore)
- Tareas: `tasks.md` sección `4. REQ-04` (4.1, 4.2)
- Estado: `templates/deploy.yml` (descarga Artifacts + SHA + SSH endurecido + cleanup ya hechos); `bat/*.bat` legacy con PAT/StrictHostKeyChecking=no (NO reescribir, solo deprecar)

## PERMITIDOS (lista exacta)

- `scripts/deploy-docker-tomcat.ps1` (nuevo)
- `scripts/deploy-docker-tomcat.sh` (nuevo)
- `templates/deploy.yml` (agregar invocación del script con versión exacta; mantener interfaz `environment/version/artifactFeed/sshTarget`)
- `bat/README.legacy.md` (nuevo, aviso de deprecación: flujo nuevo no usa `bat/`; cierre del PAT legacy)
- `tests/req04_deploy_test.py` (nuevo, TDD)
- Este contrato `docs/agent-contract/req-04-deploy.md`

## NUNCA

- `openspec/`, `bat/*.bat` (contenido intacto), `Pipeline_Script.yml`, Key Vault/Artifacts ya hechos (solo consumir), scans (REQ-05)
- Secretos reales, hosts/IPs reales nuevos (reusar `sshTarget` param), `StrictHostKeyChecking=no`, `pkill -9` incondicional
- Push a `main`, merge local a `main`

## Interfaz

- Scripts params: `WarPath, Version, SshTarget, ContainerName=default tomcat, TomcatWebapps=default /usr/local/tomcat/webapps, HealthUrl, TimeoutSec=default 120`. Sin params requeridos → uso + exit 1, sin tocar servidor.
- Flujo: verifica SHA local (re-check) → `scp` con `StrictHostKeyChecking=yes BatchMode=yes ConnectTimeout=10` → backup remoto `*.bak-<version>` → `docker cp` → `shutdown.sh` graceful (espera, solo fallback `pkill` si persiste tras timeout, logueado) → `startup.sh` → `curl --fail --max-time` healthcheck con reintentos → ante fallo: restore backup + exit 1.
- `templates/deploy.yml` invoca el script (`.sh` en agente Linux / `.ps1` en Windows via `pwsh`) con el WAR descargado de Artifacts y `HealthUrl` por entorno (variable `healthUrl_<ENV>` o param con default documentado).
- `bat/README.legacy.md`: "`bat/` deprecado; el pipeline usa `scripts/` + Artifacts; no usar con PAT".

## Verificación exacta (raíz del worktree)

```bash
python3 -m pytest tests/req04_deploy_test.py -q || python3 tests/req04_deploy_test.py
bash -n scripts/deploy-docker-tomcat.sh && echo "SH syntax OK"
pwsh -NoProfile -Command "try { [void][System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw scripts/deploy-docker-tomcat.ps1), [ref]$null) ; 'PS1 syntax OK' } catch { exit 1 }" 2>/dev/null || grep -c "ErrorActionPreference" scripts/deploy-docker-tomcat.ps1
grep -rn "StrictHostKeyChecking=no" scripts/ templates/deploy.yml && exit 1 || echo "sin SSH inseguro"
grep -rn "pkill -9" scripts/ | grep -v -i "fallback\|timeout\|if" && exit 1 || echo "sin pkill incondicional"
python3 -c "import yaml; yaml.safe_load(open('templates/deploy.yml')); print('YAML OK')"
```

TDD: RED = test falla sin scripts/wiring; GREEN = implementar; REFACTOR = deduplicar PS1/SH (funciones comunes documentadas).

## DoD

- [ ] PS1 + SH idempotentes con cabecera code-doc-standard, fail-fast, backup, healthcheck, restore.
- [ ] Template invoca script con versión exacta; sin `StrictHostKeyChecking=no`; sin `pkill -9` incondicional.
- [ ] `bat/` deprecado por escrito; flujo nuevo nunca lo llama.
- [ ] Commit en `feat/req-04-deploy` + push origin misma rama, `main` intacto.

## Reporte

`DONE` con archivos, salidas + exit codes, SHA. O `BLOCKED|NEEDS_CONTEXT` con gap exacto.
