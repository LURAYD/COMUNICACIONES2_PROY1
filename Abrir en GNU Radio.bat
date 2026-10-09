@echo off
rem ---------------------------------------------------------------------------
rem  Abre grc\validacion_gnuradio.grc en GNU Radio Companion.
rem
rem  Companion no se puede lanzar directamente (gnuradio-companion.exe muere al
rem  arrancar porque GTK no encuentra Pango sin el entorno de conda): se lanza
rem  igual que el acceso del menu Inicio, a traves de cwp.py.
rem  Para ejecutar el flowgraph: F6. Pide el parametros.txt de una corrida.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

set "RC=%USERPROFILE%\radioconda"
if defined GNURADIO_HOME set "RC=%GNURADIO_HOME%"
if not exist "%RC%\cwp.py" (
    echo.
    echo   No encuentro GNU Radio en %RC%
    echo   Define GNURADIO_HOME con la carpeta de radioconda.
    echo.
    pause
    exit /b 1
)

start "" "%RC%\pythonw.exe" "%RC%\cwp.py" "%RC%" "%RC%\Scripts\gnuradio-companion.exe" "%~dp0grc\validacion_gnuradio.grc"
