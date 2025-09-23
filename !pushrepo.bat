@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ===== ����� ���� =====
set "WORKDIR=C:\Users\pipupang\Desktop\isaac"
set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "BRANCH=main"
set "FORCE=0"
:: =======================

chcp 65001 >nul 2>&1

echo [INFO] �۾� ����: "%WORKDIR%"
echo [INFO] ���� ���� : "%REPO_URL%"
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git ��ġ Ȯ�� �ʿ�.
  goto :fail
)

pushd "%WORKDIR%" >nul 2>&1 || (echo [ERROR] ���� �̵� ���� & goto :fail)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [INFO] Git ����� �ʱ�ȭ...
  git init || goto :fail
  git branch -M "%BRANCH%" 2>nul
)

:: user.name / user.email �⺻��
git config user.name >nul 2>&1 || git config user.name "pipupang"
git config user.email >nul 2>&1 || git config user.email "pipupang@users.noreply.github.com"

:: origin ����
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin "%REPO_URL%" || goto :fail
) else (
  git remote set-url origin "%REPO_URL%" || goto :fail
)

:: �귣ġ
git rev-parse --verify "%BRANCH%" >nul 2>&1
if errorlevel 1 (
  git checkout -b "%BRANCH%" || goto :fail
) else (
  git checkout "%BRANCH%" || goto :fail
)

:: .gitignore �ڵ� ���� (���ϴ� ���� ����)
(
  echo !pushrepo.bat
  echo !getrepo.bat
  echo settings.json
) > .gitignore

:: ������� �߰�
git add -A || goto :fail

:: ���� ������ ����
git diff --cached --quiet && (
  echo [INFO] Ŀ���� ���� ����.
  goto :success
)

:: Ŀ��
for /f "usebackq tokens=* delims=" %%T in (`powershell -NoProfile -Command ^
  "[DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')"`) do set "NOW=%%T"
git commit -m "[auto] sync from Desktop\isaac - %NOW%" || goto :fail

:: Ǫ��
if "%FORCE%"=="1" (
  git push --force-with-lease -u origin "%BRANCH%" || goto :fail
) else (
  git push -u origin "%BRANCH%" || goto :fail
)

:success
echo [OK] Ǫ�� �Ϸ�!
popd >nul 2>&1
exit /b 0

:fail
echo [ERROR] ���� �߻�.
popd >nul 2>&1
pause
exit /b 1
