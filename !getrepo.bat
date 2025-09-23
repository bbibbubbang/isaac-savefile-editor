@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Isaac Savefile Editor repo updater (HARD RESET)
REM If repo exists: fetch + reset --hard to origin/(main|master)
REM If not: clone into TARGET_DIR
REM On success: exit immediately; On failure: show message and pause

set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "TARGET_DIR=C:\Users\pipupang\Desktop\isaac"

REM --- Check Git installation ---
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed. Please install from https://git-scm.com and try again.
    pause
    exit /b 1
)

REM --- If repo exists, update; else clone ---
if exist "%TARGET_DIR%\.git" (
    echo Found existing repo. Updating...

    pushd "%TARGET_DIR%" || (
        echo [ERROR] Cannot enter target dir: %TARGET_DIR%
        pause
        exit /b 1
    )

    REM Always set origin to the expected URL to avoid mismatch issues
    git remote set-url origin "%REPO_URL%"

    git fetch --all
    if errorlevel 1 (
        echo [ERROR] git fetch failed
        popd
        pause
        exit /b 1
    )

    REM Determine branch: prefer main, fallback to master
    set "BR=main"
    git ls-remote --heads origin main >nul 2>&1 || set "BR=master"

    git reset --hard origin/!BR!
    if errorlevel 1 (
        echo [ERROR] git reset --hard origin/!BR! failed
        popd
        pause
        exit /b 1
    )

    echo ==== UPDATE COMPLETE ====
    popd
    exit /b 0
) else (
    echo Repo not found. Cloning...

    if not exist "%TARGET_DIR%" (
        mkdir "%TARGET_DIR%" || (
            echo [ERROR] Could not create target dir: %TARGET_DIR%
            pause
            exit /b 1
        )
    )

    git clone "%REPO_URL%" "%TARGET_DIR%"
    if errorlevel 1 (
        echo [ERROR] git clone failed
        pause
        exit /b 1
    )

    echo ==== CLONE COMPLETE ====
    exit /b 0
)
