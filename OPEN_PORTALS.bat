@echo off
title Open All Portals
color 0B

echo.
echo ============================================================
echo    OPENING ALL PORTALS IN BROWSER
echo ============================================================
echo.

timeout /t 2 /nobreak >nul

echo Opening Student Portal...
start http://127.0.0.1:8080/frontend/student/index.html

timeout /t 1 /nobreak >nul

echo Opening Admin Portal...
start http://127.0.0.1:8080/frontend/admin/index.html

timeout /t 1 /nobreak >nul

echo Opening Gate Scanner Portal...
start http://127.0.0.1:8080/frontend/guard/index.html

echo.
echo All portals opened!
echo.
timeout /t 3 /nobreak >nul

