@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================================
REM Script: pushToAzureRepository.bat
REM Description:
REM   Pushes a WAR file to an Azure Repos Git repository.
REM   The script clones or updates the repository, copies the
REM   WAR file, commits the changes, and pushes them to main.
REM ==========================================================

REM ==========================================================
REM Validate input parameters
REM ==========================================================

if "%~3"=="" (
    echo ERROR: Invalid parameters.
    echo Usage: %~nx0 ^<BaseDirectory^> ^<PATToken^> ^<WarFilePath^>
    exit /b 1
)

REM ==========================================================
REM Assign input parameters
REM ==========================================================

set "BASE_DIRECTORY=%~1"
set "PAT_TOKEN=%~2"
set "WAR_FILE_PATH=%~3"

REM ==========================================================
REM Repository configuration
REM ==========================================================

set "REPO_NAME=deploy_DEV"
set "REPO_URL=https://%PAT_TOKEN%@dev.azure.com/organization/project/_git/Java_Application_DEV_deploy"
set "REPO_PATH=%BASE_DIRECTORY%\%REPO_NAME%"

REM ==========================================================
REM Change to base directory
REM ==========================================================

echo Changing to base directory: %BASE_DIRECTORY%
cd /d "%BASE_DIRECTORY%" || (
    echo ERROR: Failed to change directory to %BASE_DIRECTORY%
    exit /b 1
)

REM ==========================================================
REM Clone or update repository
REM ==========================================================

if exist "%REPO_PATH%" (
    echo Repository directory already exists. Updating repository...
    cd /d "%REPO_PATH%" || exit /b 1

    git reset --hard
    git pull origin main
    if errorlevel 1 (
        echo WARNING: git pull failed. Re-cloning repository...
        cd /d "%BASE_DIRECTORY%"
        rmdir /s /q "%REPO_PATH%"

        git clone "%REPO_URL%" "%REPO_NAME%"
        if errorlevel 1 (
            echo ERROR: Failed to clone repository.
            exit /b 1
        )
    ) else (
        echo Repository successfully updated.
    )
) else (
    echo Repository directory does not exist. Cloning repository...
    git clone "%REPO_URL%" "%REPO_NAME%"
    if errorlevel 1 (
        echo ERROR: Failed to clone repository.
        exit /b 1
    )
)

REM ==========================================================
REM Verify repository directory exists
REM ==========================================================

if not exist "%REPO_PATH%" (
    echo ERROR: Repository directory not found after operation.
    exit /b 1
)

REM ==========================================================
REM Copy WAR file into repository
REM ==========================================================

echo Copying WAR file: %WAR_FILE_PATH%
copy /Y "%WAR_FILE_PATH%" "%REPO_PATH%" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy WAR file.
    exit /b 1
)

REM ==========================================================
REM Change to repository directory
REM ==========================================================

cd /d "%REPO_PATH%" || exit /b 1

REM ==========================================================
REM Configure Git user (for CI/CD)
REM ==========================================================

echo Configuring Git user...
git config user.name "Azure DevOps Pipeline"
git config user.email "devops@regionmetropolitana.gov.co"

REM ==========================================================
REM Get current date and time
REM ==========================================================

for /f "tokens=1-2 delims==" %%a in ('wmic os get localdatetime /value') do (
    if "%%a"=="LocalDateTime" set "LDT=%%b"
)

set "CURRENT_DATETIME=!LDT:~0,4!-!LDT:~4,2!-!LDT:~6,2! !LDT:~8,2!:!LDT:~10,2!:!LDT:~12,2!"
echo Current date and time: %CURRENT_DATETIME%

REM ==========================================================
REM Commit and push changes
REM ==========================================================

echo Committing and pushing changes to Azure Repos...
git add .
git commit -m "Automated deployment - %CURRENT_DATETIME%"
if errorlevel 1 (
    echo ERROR: Git commit failed.
    exit /b 1
)

git push origin main
if errorlevel 1 (
    echo ERROR: Git push failed.
    exit /b 1
)

REM ==========================================================
REM Completed
REM ==========================================================

echo WAR file successfully pushed to Azure Repos.

endlocal
exit /b 0
