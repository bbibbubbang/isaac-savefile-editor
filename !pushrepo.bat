@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ===== ���� =====
set "WORKDIR=C:\Users\pipupang\Desktop\isaac"
set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "BRANCH=main"
set "FORCE=0"
:: ================

chcp 65001 >nul 2>&1
echo [Autopush] ����

where git >nul 2>&1 || (echo [Autopush] Git ��ġ �ʿ� & goto :fail)
pushd "%WORKDIR%" >nul 2>&1 || (echo [Autopush] ���� �̵� ���� & goto :fail)

:: ����� �غ�
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [Autopush] ����� �ʱ�ȭ
  git init || goto :fail
  git branch -M "%BRANCH%" 2>nul
)

git config user.name >nul 2>&1 || git config user.name "pipupang"
git config user.email >nul 2>&1 || git config user.email "pipupang@users.noreply.github.com"

git remote get-url origin >nul 2>&1
if errorlevel 1 ( git remote add origin "%REPO_URL%" ) else ( git remote set-url origin "%REPO_URL%" ) || goto :fail

git rev-parse --verify "%BRANCH%" >nul 2>&1
if errorlevel 1 ( git checkout -b "%BRANCH%" ) else ( git checkout "%BRANCH%" ) || goto :fail

:: ----- ���� ���� ���� ��Ģ: .gitignore�� ������ ���� -----
if not exist ".git\info" mkdir ".git\info" >nul 2>&1
if not exist ".git\info\exclude" type nul > ".git\info\exclude"

:: .gitignore ��ü�� ���� ����
findstr /x /c:".gitignore" ".git\info\exclude" >nul 2>&1 || echo .gitignore>>".git\info\exclude"

:: ���� ������ ���ϵ� (���� '!'�� ���ͷ��� ����Ϸ��� \! �� �̽�������)
findstr /x /c:"\!pushrepo.bat" ".git\info\exclude" >nul 2>&1 || echo \!pushrepo.bat>>".git\info\exclude"
findstr /x /c:"\!getrepo.bat"  ".git\info\exclude" >nul 2>&1 || echo \!getrepo.bat>>".git\info\exclude"
findstr /x /c:"settings.json"  ".git\info\exclude" >nul 2>&1 || echo settings.json>>".git\info\exclude"

:: �̹� ���� ���� ��� �ε������� ���� (���ݿ��� ����, ���� ���� ����)
for %%F in (".gitignore" "!pushrepo.bat" "!getrepo.bat" "settings.json") do (
  git ls-files --error-unmatch "%%~F" >nul 2>&1 && git rm --cached "%%~F" >nul
)

:: ���ÿ� �����ִ� .gitignore ���� ����(������)
attrib -r ".gitignore" >nul 2>&1
del /f /q ".gitignore" >nul 2>&1

:: -----------------------------------------------

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
