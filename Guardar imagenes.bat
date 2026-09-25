@echo off
rem ---------------------------------------------------------------------------
rem  Guarda las imagenes SIN abrir la interfaz.
rem
rem  Corre la simulacion, renderiza los instrumentos fuera de pantalla y escribe
rem  las figuras y las medidas en la carpeta resultados_app\. No aparece ninguna
rem  ventana. Aqui si se usa python.exe (con consola) para que se vea el avance.
rem
rem  Para otra configuracion, desde la linea de ordenes:
rem     .venv\Scripts\python -m app --export salida --escenario B --ebn0 14 --eq rls
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo.
    echo   No se encuentra el entorno virtual en .venv
    echo   Crealo con:  python -m venv .venv  ^&^&  .venv\Scripts\activate  ^&^&  pip install -e .[gui]
    echo.
    pause
    exit /b 1
)

"%PY%" -m app --export resultados_app
echo.
pause
