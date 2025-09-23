@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ===== 설정 =====
set "WORKDIR=C:\Users\pipupang\Desktop\isaac"
set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "BRANCH=main"
set "FORCE=0"
:: ================

chcp 65001 >nul 2>&1
echo [Autopush] 시작

where git >nul 2>&1 || (echo [Autopush] Git 설치 필요 & goto :fail)
pushd "%WORKDIR%" >nul 2>&1 || (echo [Autopush] 폴더 이동 실패 & goto :fail)

:: 저장소 준비
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [Autopush] 저장소 초기화
  git init || goto :fail
  git branch -M "%BRANCH%" 2>nul
)

git config user.name >nul 2>&1 || git config user.name "pipupang"
git config user.email >nul 2>&1 || git config user.email "pipupang@users.noreply.github.com"

git remote get-url origin >nul 2>&1
if errorlevel 1 ( git remote add origin "%REPO_URL%" ) else ( git remote set-url origin "%REPO_URL%" ) || goto :fail

git rev-parse --verify "%BRANCH%" >nul 2>&1
if errorlevel 1 ( git checkout -b "%BRANCH%" ) else ( git checkout "%BRANCH%" ) || goto :fail

:: ----- 로컬 전용 무시 규칙: .gitignore는 만들지 않음 -----
if not exist ".git\info" mkdir ".git\info" >nul 2>&1
if not exist ".git\info\exclude" type nul > ".git\info\exclude"

:: .gitignore 자체도 추적 금지
findstr /x /c:".gitignore" ".git\info\exclude" >nul 2>&1 || echo .gitignore>>".git\info\exclude"

:: 실제 무시할 파일들 (앞의 '!'를 리터럴로 취급하려면 \! 로 이스케이프)
findstr /x /c:"\!pushrepo.bat" ".git\info\exclude" >nul 2>&1 || echo \!pushrepo.bat>>".git\info\exclude"
findstr /x /c:"\!getrepo.bat"  ".git\info\exclude" >nul 2>&1 || echo \!getrepo.bat>>".git\info\exclude"
findstr /x /c:"settings.json"  ".git\info\exclude" >nul 2>&1 || echo settings.json>>".git\info\exclude"

:: 이미 추적 중인 경우 인덱스에서 제거 (원격에서 삭제, 로컬 파일 유지)
for %%F in (".gitignore" "!pushrepo.bat" "!getrepo.bat" "settings.json") do (
  git ls-files --error-unmatch "%%~F" >nul 2>&1 && git rm --cached "%%~F" >nul
)

:: 로컬에 남아있는 .gitignore 강제 삭제(있으면)
attrib -r ".gitignore" >nul 2>&1
del /f /q ".gitignore" >nul 2>&1

:: -----------------------------------------------

git add -A || goto :fail

git diff --cached --quiet && (
  echo [Autopush] 변경 없음
  goto :success
)

git commit -m "[Autopush]" || goto :fail

if "%FORCE%"=="1" (
  git push --force-with-lease -u origin "%BRANCH%" || goto :fail
) else (
  git push -u origin "%BRANCH%" || goto :fail
)

:success
echo [Autopush] 완료
popd >nul 2>&1
exit /b 0

:fail
echo [Autopush] 오류
popd >nul 2>&1
pause
exit /b 1
