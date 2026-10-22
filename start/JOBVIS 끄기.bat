@echo off
chcp 65001 >nul
setlocal
rem JOBVIS 끄기 (v0.6.2 F3). 데이터(키, 프로필, 공고, 점수)는 볼륨에 남는다.
cd /d "%~dp0"
title JOBVIS 끄기
if not exist "jobvis.env" (> "jobvis.env" echo JOBVIS_TAG=latest)
docker compose -f compose.yml --env-file jobvis.env down
if errorlevel 1 (
    echo.
    echo 끄지 못했습니다. Docker Desktop이 켜져 있는지 확인하세요.
    pause
    exit /b 1
)
echo JOBVIS를 껐습니다. 데이터는 남아 있습니다.
timeout /t 3 >nul
