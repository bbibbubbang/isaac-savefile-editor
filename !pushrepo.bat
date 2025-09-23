@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ===== ����� ���� =====
set "WORKDIR=C:\Users\pipupang\Desktop\isaac"
set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "BRANCH=main"
set "FORCE=0"
:: =======================

chcp 65001 >nul 2>&1

echo [Autopush] ����

where git >nul 2>&1
if errorlevel 1 (
  echo [Autopush] Git ��ġ �ʿ�
  goto :fail
)

pushd "%WORKDIR%" >nul 2>&1 || (echo [Autopush] ���� �̵� ���� & goto :fail)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [Autopush] ����� �ʱ�ȭ
  git init || goto :fail
  git branch -M "%BRANCH%" 2>nul
)

git config user.name >nul 2>&1 || git config user.name "pipupang"
git config user.email >nul 2>&1 || git config user.email "pipupang@users.noreply.github.com"

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin "%REPO_URL%" || goto :fail
) else (
  git remote set-url origin "%REPO_URL%" || goto :fail
)

git rev-parse --verify "%BRANCH%" >nul 2>&1
if errorlevel 1 (
  git checkout -b "%BRANCH%" || goto :fail
) else (
  git checkout "%BRANCH%" || goto :fail
)

:: .gitignore ���� (������ ���ϵ�)
(
  echo !pushrepo.bat
  echo !getrepo.bat
  echo settings.json
) > .gitignore

git add -A || goto :fail

git diff --cached --quiet && (
  echo [Autopush] ���� ����
  goto :success
)

git commit -m "[Autopush]" || goto :fail

if "%FORCE%"=="1" (
  git push --force-with-lease -u origin "%BRANCH%" || goto :fail
) else (
  git push -u origin "%BRANCH%" || goto :fail
)

:success
echo [Autopush] �Ϸ�
popd >nul 2>&1
exit /b 0

:fail
echo [Autopush] ����
popd >nul 2>&1
pause
exit /b 1
