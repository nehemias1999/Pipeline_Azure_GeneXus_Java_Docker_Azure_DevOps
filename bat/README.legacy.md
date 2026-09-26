# `bat/` deprecado (legacy)

> **Aviso:** los scripts de este directorio (`deployOnRemoteDockerContainer.bat`,
> `pushToAzureRepository.bat`) estan **deprecados** y se conservan solo como
> referencia historica. **El pipeline usa `scripts/` + Artifacts; no usar con PAT.**
>
> - El flujo nuevo nunca llama a `bat/`: `templates/deploy.yml` invoca
>   `scripts/deploy-docker-tomcat.sh` (agente Linux) o
>   `scripts/deploy-docker-tomcat.ps1` (agente Windows via `pwsh`) con el WAR
>   descargado de Azure Artifacts por version exacta y SHA256 verificado.
> - Los `.bat` legacy embebian PAT en URL/CLI y usaban `StrictHostKeyChecking=no`;
>   ambos patrones estan prohibidos (REQ-02/REQ-04). Cierre del PAT legacy:
>   revocar cualquier token personal usado por estos scripts y operar solo con
>   `System.AccessToken` + Key Vault.
> - No modificar ni reactivar estos archivos; cualquier cambio de deploy va en
>   `scripts/deploy-docker-tomcat.*` con su test en `tests/req04_deploy_test.py`.
