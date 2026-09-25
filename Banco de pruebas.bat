@echo off
rem ---------------------------------------------------------------------------
rem  Receptor digital adaptativo - Banco de pruebas
rem  Proyecto 1, Comunicaciones II 2026
rem
rem  Doble clic para abrir. Usa pythonw.exe para que no aparezca una ventana de
rem  consola detras de la aplicacion; si algo falla, el propio programa muestra
rem  el error en un cuadro de dialogo en lugar de cerrarse en silencio.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

set "PY=.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo.
    echo   No se encuentra el entorno virtual en .venv
    echo.
    echo   Crealo una sola vez con:
    echo.
    echo       python -m venv .venv
    echo       .venv\Scripts\activate
    echo       pip install -e .
    echo       pip install PySide6 pyqtgraph
    echo.
    pause
    exit /b 1
)

start "" "%PY%" -m app
