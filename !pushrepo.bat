@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ===== 사용자 설정 =====
set "WORKDIR=C:\Users\pipupang\Desktop\isaac"
set "REPO_URL=https://github.com/bbibbubbang/isaac-savefile-editor"
set "BRANCH=main"
set "FORCE=0"
:: =======================

chcp 65001 >nul 2>&1

echo [INFO] 작업 폴더: "%WORKDIR%"
echo [INFO] 원격 레포 : "%REPO_URL%"
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git 설치 확인 필요.
  goto :fail
)

pushd "%WORKDIR%" >nul 2>&1 || (echo [ERROR] 폴더 이동 실패 & goto :fail)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [INFO] Git 저장소 초기화...
  git init || goto :fail
  git branch -M "%BRANCH%" 2>nul
)

:: user.name / user.email 기본값
git config user.name >nul 2>&1 || git config user.name "pipupang"
git config user.email >nul 2>&1 || git config user.email "pipupang@users.noreply.github.com"

:: origin 설정
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin "%REPO_URL%" || goto :fail
) else (
  git remote set-url origin "%REPO_URL%" || goto :fail
)

:: 브랜치
git rev-parse --verify "%BRANCH%" >nul 2>&1
if errorlevel 1 (
  git checkout -b "%BRANCH%" || goto :fail
) else (
  git checkout "%BRANCH%" || goto :fail
)

:: .gitignore 자동 생성 (원하는 파일 제외)
(
  echo !pushrepo.bat
  echo !getrepo.bat
  echo settings.json
) > .gitignore

:: 변경사항 추가
git add -A || goto :fail

:: 변경 없으면 종료
git diff --cached --quiet && (
  echo [INFO] 커밋할 변경 없음.
  goto :success
)

:: 커밋
for /f "usebackq tokens=* delims=" %%T in (`powershell -NoProfile -Command ^
  "[DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')"`) do set "NOW=%%T"
git commit -m "[auto] sync from Desktop\isaac - %NOW%" || goto :fail

:: 푸시
if "%FORCE%"=="1" (
  git push --force-with-lease -u origin "%BRANCH%" || goto :fail
) else (
  git push -u origin "%BRANCH%" || goto :fail
)

:success
echo [OK] 푸시 완료!
popd >nul 2>&1
exit /b 0

:fail
echo [ERROR] 오류 발생.
popd >nul 2>&1
pause
exit /b 1
