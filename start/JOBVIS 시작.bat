@echo off
chcp 65001 >nul
setlocal
rem JOBVIS 시작 (v0.6.2 F1-F6). 이 파일과 compose.yml이 같은 폴더에 있어야 한다.
rem 키는 이 파일에서 다루지 않는다. 화면 첫 창에서 넣는다 (v0.6.1).
cd /d "%~dp0"
title JOBVIS 시작
set "SETTINGS=jobvis.env"

echo [1/4] Docker 확인 중...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo Docker가 꺼져 있거나 설치돼 있지 않습니다.
    echo Docker Desktop을 켠 뒤 다시 실행하세요.
    goto fail
)

if not exist "%SETTINGS%" (
    call :ask_ocr
) else (
    choice /c YN /t 5 /d N /m "OCR 설정을 바꿀까요? 5초 안에 Y, 그대로면 기다리세요"
    if not errorlevel 2 call :ask_ocr
)

echo [2/4] 8501 포트 확인 중...
docker compose --env-file "%SETTINGS%" ps --status running --services 2>nul | findstr /x "app" >nul
if errorlevel 1 (
    netstat -ano | findstr /r /c:":8501 .*LISTENING" >nul
    if not errorlevel 1 (
        echo.
        echo 8501 포트를 다른 프로그램이 쓰고 있습니다.
        echo 다른 JOBVIS 창이나 streamlit을 끄거나 PC를 다시 켠 뒤 실행하세요.
        goto fail
    )
)

echo [3/4] 이미지 받는 중... 처음에는 몇 분 걸립니다.
docker compose --env-file "%SETTINGS%" pull
if errorlevel 1 (
    echo.
    echo 이미지를 받지 못했습니다. 인터넷 연결을 확인하고 다시 실행하세요.
    goto fail
)

echo [4/4] JOBVIS 켜는 중... 화면이 준비될 때까지 기다립니다.
docker compose --env-file "%SETTINGS%" up -d --wait
if errorlevel 1 (
    echo.
    echo JOBVIS를 켜지 못했습니다. 아래 기록을 확인하세요.
    docker compose --env-file "%SETTINGS%" logs --tail 30 app
    goto fail
)

echo.
echo JOBVIS가 켜졌습니다: http://localhost:8501
echo 끌 때는 "JOBVIS 끄기.bat"을 실행하세요. 데이터는 남습니다.
start "" http://localhost:8501
timeout /t 5 >nul
exit /b 0

:ask_ocr
echo.
echo 공고 본문이 이미지인 경우 글자를 읽는 OCR을 같이 받을 수 있습니다(약 350MB 더).
echo 나중에 이 파일을 다시 열어 바꿀 수 있습니다.
choice /c YN /m "OCR도 받을까요"
if errorlevel 2 (
    > "%SETTINGS%" echo JOBVIS_TAG=latest
    echo OCR 없이 씁니다.
) else (
    > "%SETTINGS%" echo JOBVIS_TAG=ocr
    echo OCR 포함으로 씁니다.
)
exit /b 0

:fail
echo.
pause
exit /b 1
