@echo off
rem ---------------------------------------------------------------------------
rem  Instalacion del proyecto (una sola vez)
rem  Proyecto 1, Comunicaciones II 2026
rem
rem  Busca Python 3.10 o posterior, crea el entorno .venv en esta carpeta e
rem  instala el simulador y la aplicacion. Despues: "Banco de pruebas.bat".
rem ---------------------------------------------------------------------------
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
    echo   No se encuentra Python 3.10 o posterior.
    echo   Instalalo desde https://www.python.org/downloads/ marcando
    echo   "Add python.exe to PATH" y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)
echo   Usando: %PYBASE%

if not exist ".venv\Scripts\python.exe" (
    echo   Creando el entorno .venv ...
    %PYBASE% -m venv .venv || goto :error
)

echo   Instalando dependencias (la primera vez tarda unos minutos) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul || goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
".venv\Scripts\python.exe" -m pip install -e . pytest || goto :error

echo.
echo   Comprobando que el simulador funciona ...
".venv\Scripts\python.exe" -c "import comm2, PySide6, pyqtgraph; print('   comm2', comm2.__version__, '- todo instalado')" || goto :error

echo.
echo   Listo. Para abrir la aplicacion: doble clic en "Banco de pruebas.bat".
echo   La parte de GNU Radio necesita ademas radioconda (ver INSTALAR.md).
echo.
pause
exit /b 0

:error
echo.
echo   La instalacion fallo. Revisa el mensaje de arriba.
echo.
pause
exit /b 1
