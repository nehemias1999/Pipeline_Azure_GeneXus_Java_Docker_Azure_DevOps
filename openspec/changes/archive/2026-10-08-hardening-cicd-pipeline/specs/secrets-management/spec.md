# Spec Delta

## Purpose

Garantiza que ningún secreto viva en el repo ni se filtre en logs, centralizando credenciales en Azure Key Vault y endureciendo el acceso SSH.

## ADDED Requirements

### Requirement: Secretos centralizados en Key Vault

El sistema SHALL resolver `ServerPassword`, `ApplicationKey`, `PATToken`/`System.AccessToken` y la llave SSH privada desde Azure Key Vault (via Variable Group linkeada) y SHALL fallar si alguna variable secreta está vacía. Ningún secreto SHALL aparecer en texto plano en YAML, scripts o logs.

#### Scenario: Sin secretos en el repo

- **WHEN** se ejecuta `gitleaks detect --source . --verbose` y `grep -r ApplicationKey`
- **THEN** no se reporta ningún hallazgo y la llave histórica queda rotada

#### Scenario: Secretos enmascarados en logs

- **WHEN** corre el pipeline con `System.Debug=true`
- **THEN** los valores secretos aparecen como `***` y el PAT nunca forma parte de una URL clonada (se usa `System.AccessToken` o `AzureCLI`)

### Requirement: SSH endurecido con llaves y host verificado

El sistema SHALL conectar por SSH con llave privada desde Key Vault, `StrictHostKeyChecking=yes` con `known_hosts` versionado, `BatchMode=yes` y `ConnectTimeout`, y SHALL rechazar conexiones si el fingerprint del host no coincide.

#### Scenario: MITM bloqueado

- **WHEN** el fingerprint del host remoto cambia
- **THEN** el deploy falla explícitamente en lugar de conectar
