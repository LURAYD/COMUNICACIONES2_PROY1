# Cómo instalarlo

Proyecto 1 de Comunicaciones II. Lo probé en Windows.

## Lo básico

1. Instala Python 3.10 o más nuevo (python.org). Marca "Add python.exe to PATH".
2. Descomprime el zip en una carpeta corta, por ejemplo `C:\comunicacion`.
   Si la ruta es muy larga, la instalación falla.
3. Doble clic en `Instalar.bat`. La primera vez tarda unos minutos.
4. Doble clic en `Banco de pruebas.bat` y listo.

## GNU Radio (opcional)

1. Instala radioconda (github.com/radioconda/radioconda-installer) con la
   carpeta que trae por defecto.
2. `Abrir en GNU Radio.bat` abre el flowgraph. Con F6 corre y te pide una
   corrida; hay una de ejemplo en `grc\corridas\ejemplo`.
3. `Validar GNU Radio.bat` compara GNU Radio con Python y guarda una tabla y
   una gráfica en la carpeta de la corrida.

Más detalles en `grc\README.md`.

## Carpetas

- `src\comm2`: el simulador
- `app`: el programa con ventana
- `experiments` y `results`: los experimentos y sus gráficas
- `grc`: lo de GNU Radio
- `presentacion`: la presentación

El libro en PDF no va incluido porque pesa demasiado.
