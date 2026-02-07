@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================================
REM Script: deployOnRemoteDockerContainer.bat
REM Description: 
REM   Copies a WAR file to a remote server and deploys it into
REM   a Docker container running Apache Tomcat.
REM ==========================================================

REM ==========================================================
REM Validate input parameters
REM ==========================================================

if "%~3"=="" (
    echo ERROR: Invalid parameters.
    echo Usage: %~nx0 ^<RemoteUser^> ^<RemoteHost^> ^<WarFilePath^>
    exit /b 1
)

REM ==========================================================
REM Assign input parameters
REM ==========================================================

set "REMOTE_USER=%~1"
set "REMOTE_HOST=%~2"
set "WAR_FILE_PATH=%~3"

REM ==========================================================
REM Remote and container configuration
REM ==========================================================

set "REMOTE_TEMP_DIR=~"
set "CONTAINER_NAME=tomcat"
set "TOMCAT_DEPLOY_DIR=/usr/local/tomcat/webapps"
set "TOMCAT_BIN_DIR=/usr/local/tomcat/bin"

REM ==========================================================
REM SSH options (non-interactive, CI/CD friendly)
REM ==========================================================

set "SSH_OPTS=-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10"

REM ==========================================================
REM Extract WAR file name and base name
REM ==========================================================

for %%F in ("%WAR_FILE_PATH%") do (
    set "WAR_FILE_NAME=%%~nxF"
    set "WAR_BASE_NAME=%%~nF"
)

REM ==========================================================
REM Copy WAR file to remote server
REM ==========================================================

echo Copying WAR file to remote server...
scp %SSH_OPTS% "%WAR_FILE_PATH%" %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_TEMP_DIR%/
if errorlevel 1 (
    echo ERROR: Failed to copy WAR file to remote server.
    exit /b 1
)

REM ==========================================================
REM Stop Tomcat inside the Docker container
REM ==========================================================

echo Stopping Tomcat inside Docker container...
ssh %SSH_OPTS% %REMOTE_USER%@%REMOTE_HOST% ^
    "docker exec %CONTAINER_NAME% sh -c 'cd %TOMCAT_BIN_DIR% && ./shutdown.sh'"

if errorlevel 1 (

    echo WARNING: shutdown.sh returned an error. Continuing anyway...

) else (

    echo Tomcat shutdown script executed successfully.
    echo Waiting 5 seconds for processes to terminate...
    timeout /t 5 >nul

)

REM ==========================================================
REM Force stop Tomcat if any process remains
REM ==========================================================

echo Forcing Tomcat shutdown if any process remains...
ssh %SSH_OPTS% %REMOTE_USER%@%REMOTE_HOST% ^
    "docker exec %CONTAINER_NAME% pkill -9 -f 'org.apache.catalina.startup.Bootstrap'"

if errorlevel 1 (

    echo ERROR: Failed to force-stop Tomcat processes.
    exit /b 1

)

REM ==========================================================
REM Remove previous WAR and exploded directory if they exist
REM ==========================================================

echo Removing previous WAR and exploded directory (if any)...
ssh %SSH_OPTS% %REMOTE_USER%@%REMOTE_HOST% ^
    "docker exec %CONTAINER_NAME% sh -c ^
    'if [ -f %TOMCAT_DEPLOY_DIR%/%WAR_FILE_NAME% ]; then rm -f %TOMCAT_DEPLOY_DIR%/%WAR_FILE_NAME%; fi; ^
     if [ -d %TOMCAT_DEPLOY_DIR%/%WAR_BASE_NAME% ]; then rm -rf %TOMCAT_DEPLOY_DIR%/%WAR_BASE_NAME%; fi'"

if errorlevel 1 (

    echo ERROR: Failed to remove previous deployment.
    exit /b 1

)

REM ==========================================================
REM Copy WAR file into the Docker container
REM ==========================================================

echo Copying WAR file into Docker container...
ssh %SSH_OPTS% %REMOTE_USER%@%REMOTE_HOST% ^
    "docker cp %REMOTE_TEMP_DIR%/%WAR_FILE_NAME% %CONTAINER_NAME%:%TOMCAT_DEPLOY_DIR%/"

if errorlevel 1 (

    echo ERROR: Failed to copy WAR file into Docker container.
    exit /b 1

)

REM ==========================================================
REM Start Tomcat inside the Docker container
REM ==========================================================

echo Starting Tomcat inside Docker container...
ssh %SSH_OPTS% %REMOTE_USER%@%REMOTE_HOST% ^
    "docker exec %CONTAINER_NAME% sh -c 'cd %TOMCAT_BIN_DIR% && ./startup.sh'"

if errorlevel 1 (

    echo ERROR: Failed to start Tomcat inside the container.
    exit /b 1

)

REM ==========================================================
REM Deployment completed
REM ==========================================================

echo Deployment completed successfully.

endlocal
exit /b 0