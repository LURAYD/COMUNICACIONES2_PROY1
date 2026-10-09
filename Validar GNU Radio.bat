@echo off
rem ---------------------------------------------------------------------------
rem  Validacion cruzada Python - GNU Radio (seccion 11 de la guia)
rem  Proyecto 1, Comunicaciones II 2026
rem
rem  Doble clic: valida la corrida mas reciente de grc\corridas.
rem  Arrastrar encima una carpeta de corrida o el JSON que exporta la
rem  aplicacion (seccion Exportar): valida esa.
rem  Deja la tabla y la figura en <corrida>\comparacion.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
chcp 65001 >nul

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo.
    echo   No se encuentra el entorno virtual en .venv
    echo.
    pause
    exit /b 1
)

"%PY%" grc\validar_gnuradio.py %*
echo.
pause
