<#
Description: Despliega un WAR verificado por SHA256 en Tomcat dentro de un
  contenedor Docker remoto via SSH endurecido. Flujo idempotente: re-chequea
  el SHA local, copia con scp, respalda la version previa (*.bak-<version>),
  apaga Tomcat graceful (pkill solo como fallback tras timeout, logueado),
  enciende y verifica healthcheck HTTP con reintentos; ante fallo restaura
  el backup y sale 1. Gemelo del .sh para agentes Windows. Reemplaza los
  .bat legacy (ver bat/README.legacy.md).
Usage: .\deploy-docker-tomcat.ps1 -WarPath <app.war> -Version <1.0.42>
  -SshTarget <usuario@host> [-ContainerName tomcat]
  [-TomcatWebapps /usr/local/tomcat/webapps] [-HealthUrl <url>]
  [-TimeoutSec 120]
Env Vars: ninguna requerida. El caller (templates/deploy.yml) resuelve
  healthUrl_<ENV> y lo pasa como -HealthUrl.
Dependencies: PowerShell 7+, ssh, scp, curl (OpenSSH/OpenSSL del agente);
  docker, pgrep, pkill en el host remoto (pkill solo fallback);
  Tomcat con shutdown.sh/startup.sh.
Output / Exit codes: salida informativa a STDOUT, errores a STDERR.
  0 = deploy + healthcheck OK; 1 = params invalidos, WAR/SHA invalidos,
  copia, ciclo Tomcat, healthcheck (con restore) o SSH fallidos.
  Default -HealthUrl: http://localhost:8080/ (curleado EN el servidor).
#>
$ErrorActionPreference = 'Stop'

param(
  [string]$WarPath = '',
  [string]$Version = '',
  [string]$SshTarget = '',
  [string]$ContainerName = 'tomcat',
  [string]$TomcatWebapps = '/usr/local/tomcat/webapps',
  [string]$HealthUrl = '',
  [int]$TimeoutSec = 120
)

function Show-Usage {
  @'
Usage: deploy-docker-tomcat.ps1 -WarPath <app.war> -Version <x.y.z> -SshTarget <usuario@host> [opciones]

Despliega un WAR en Tomcat/Docker remoto con backup y healthcheck.

  -WarPath <ruta>       WAR a desplegar (requerido, debe existir)
  -Version <ver>        Version exacta, p.ej. 1.0.42 (requerido)
  -SshTarget <u@h>      Destino SSH, p.ej. deploy@tomcat-dev (requerido)
  -ContainerName <n>    Contenedor Docker (default: tomcat)
  -TomcatWebapps <ruta> webapps en el contenedor (default: /usr/local/tomcat/webapps)
  -HealthUrl <url>      Endpoint de salud (default: http://localhost:8080/)
  -TimeoutSec <n>       Timeout graceful + healthcheck (default: 120)
'@
}

# Fail-fast: sin params requeridos se imprime uso y se sale 1 sin tocar el servidor.
if ([string]::IsNullOrWhiteSpace($WarPath) -or [string]::IsNullOrWhiteSpace($Version) -or [string]::IsNullOrWhiteSpace($SshTarget)) {
  [Console]::Error.WriteLine('error: -WarPath, -Version y -SshTarget son requeridos')
  Show-Usage
  exit 1
}
if ([string]::IsNullOrWhiteSpace($HealthUrl)) { $HealthUrl = 'http://localhost:8080/' }

# Fail-fast local: el WAR debe existir ANTES de tocar el servidor.
if (-not (Test-Path -Path $WarPath -PathType Leaf)) {
  [Console]::Error.WriteLine("error: WAR no encontrado: $WarPath")
  exit 1
}

# Re-check SHA256 local si viaja el .sha256 hermano (REQ-03 lo publica).
$shaFile = "$WarPath.sha256"
if (Test-Path -Path $shaFile -PathType Leaf) {
  $expected = ((Get-Content -Raw $shaFile) -split '\s+')[0]
  $actual = (Get-FileHash -Path $WarPath -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $expected.ToLower()) {
    [Console]::Error.WriteLine("error: SHA256 mismatch en $WarPath")
    exit 1
  }
  Write-Output "SHA256 local OK: $WarPath"
}

$appName = [System.IO.Path]::GetFileNameWithoutExtension($WarPath)
$remoteTmp = "/tmp/${appName}-${Version}.war"
$sshOpts = @('-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')

Write-Output "Copiando $WarPath a ${SshTarget}:${remoteTmp}"
& scp @sshOpts $WarPath "${SshTarget}:${remoteTmp}"
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine('error: scp fallo'); exit 1 }

Write-Output "Desplegando version $Version en contenedor $ContainerName"
$remoteScript = @"
set -euo pipefail
TARGET='$TomcatWebapps/$appName.war'
PREV='$TomcatWebapps/$appName.war.bak-$Version'
if [ -f "`$TARGET" ]; then cp --force "`$TARGET" "`$PREV"; echo "backup previo en `$PREV"; fi
docker cp '$remoteTmp' '$ContainerName:`$TARGET'
rm --force '$remoteTmp'
docker exec '$ContainerName' '$TomcatWebapps/../bin/shutdown.sh' || true
waited=0
while docker exec '$ContainerName' pgrep -f catalina >/dev/null 2>&1; do
  if [ "`$waited" -ge '$TimeoutSec' ]; then break; fi
  sleep 5; waited=`$((waited + 5))
done
if docker exec '$ContainerName' pgrep -f catalina >/dev/null 2>&1; then
  echo 'WARN: shutdown graceful excedio el timeout, fallback pkill (logueado)' >&2 # fallback tras timeout
  docker exec '$ContainerName' pkill -9 -f catalina || true # fallback tras timeout
  sleep 5
fi
docker exec '$ContainerName' '$TomcatWebapps/../bin/startup.sh'
attempts=`$(( ('$TimeoutSec' + 9) / 10 ))
ok=0
for ((i = 1; i <= attempts; i++)); do
  if docker exec '$ContainerName' curl --fail --silent --max-time 10 '$HealthUrl' >/dev/null 2>&1; then
    ok=1; echo "healthcheck OK (intento `$i/`$attempts): $HealthUrl"; break
  fi
  echo "healthcheck intento `$i/`$attempts sin 200, reintentando..."; sleep 10
done
if [ "`$ok" -ne 1 ]; then
  echo "ERROR: healthcheck fallo, restaurando backup" >&2
  if [ -f "`$PREV" ]; then
    docker cp "`$PREV" '$ContainerName:`$TARGET'
    docker exec '$ContainerName' '$TomcatWebapps/../bin/startup.sh' || true
    echo "backup restaurado desde `$PREV" # restore del backup previo
  fi
  exit 1
fi
"@
$remoteScript | & ssh @sshOpts $SshTarget 'bash -s'
if ($LASTEXITCODE -ne 0) { [Console]::Error.WriteLine('error: deploy remoto fallo'); exit 1 }

Write-Output "Deploy $Version OK con healthcheck en $HealthUrl"
