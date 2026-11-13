@echo off
title news
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
:loop
%PY% run_local.py
if %errorlevel%==0 exit /b 0
if %errorlevel%==3 goto again
echo.
echo news stopped with an error. Details are above and in out\run.log.
echo Trying again in 30 seconds. Close this window to stop.
timeout /t 30 /nobreak >nul
:again
set "PF_RESTART=1"
goto loop
:nopython
echo Python is not installed.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this file again.
pause
exit /b 1
