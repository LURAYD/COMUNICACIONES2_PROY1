@echo off
rem Instala el proyecto (solo la primera vez).
cd /d "%~dp0"
chcp 65001 >nul

set "PYBASE="
for %%V in (3.12 3.11 3.10 3.13) do (
    if not defined PYBASE (
        py -%%V -c "import sys" >nul 2>&1 && set "PYBASE=py -%%V"
    )
)
if not defined PYBASE (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYBASE=python"
)
if not defined PYBASE (
    echo.
    echo   No encuentro Python 3.10 o mas nuevo. Instalalo desde python.org
    echo   ^(marca "Add python.exe to PATH"^) y vuelve a abrir esto.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo   Creando el entorno...
    %PYBASE% -m venv .venv || goto :error
)

echo   Instalando, tarda unos minutos...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul || goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
".venv\Scripts\python.exe" -m pip install -e . pytest || goto :error
".venv\Scripts\python.exe" -c "import comm2, PySide6, pyqtgraph" || goto :error

echo.
echo   Listo. Abre "Banco de pruebas.bat".
echo.
pause
exit /b 0

:error
echo.
echo   Algo fallo. Si dice "filename too long", mueve la carpeta a una ruta
echo   corta como C:\comunicacion, borra la carpeta .venv y vuelve a probar.
echo.
pause
exit /b 1
