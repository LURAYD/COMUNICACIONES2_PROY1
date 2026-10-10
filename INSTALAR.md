# Cómo instalar y usar el proyecto

Proyecto 1 de Comunicaciones II 2026: simulador de un receptor digital
adaptativo, aplicación de escritorio para manejarlo en vivo y validación
cruzada con GNU Radio. Probado en Windows 10/11.

## 1. Lo mínimo: simulador y aplicación

1. Instala **Python 3.10 o posterior** desde https://www.python.org/downloads/
   y marca la casilla *«Add python.exe to PATH»*.
2. Descomprime el zip en una carpeta. Mejor una ruta sin espacios raros, por
   ejemplo `C:\comunicacion`.
3. Doble clic en **`Instalar.bat`**. Crea el entorno `.venv` e instala todo.
   La primera vez tarda unos minutos, porque PySide6 ocupa bastante.
4. Doble clic en **`Banco de pruebas.bat`**. La ventana aparece en unos
   segundos.

## 2. La parte de GNU Radio (opcional)

1. Instala **radioconda**, que trae GNU Radio 3.10:
   https://github.com/radioconda/radioconda-installer/releases. Usa la ruta
   que propone (`C:\Users\<usuario>\radioconda`). Si la instalas en otra,
   define la variable de entorno `GNURADIO_HOME` con esa carpeta.
2. **`Abrir en GNU Radio.bat`**: abre el flowgraph en GNU Radio Companion.
   Pulsa **F6** para ejecutarlo y elige el `parametros.txt` de una corrida
   (hay una de ejemplo en `grc\corridas\ejemplo`).
3. **`Validar GNU Radio.bat`**: ejecuta GNU Radio sin ventanas y compara con
   Python. Deja la tabla y la figura en `<corrida>\comparacion\`. También se le
   puede arrastrar encima el JSON que exporta la aplicación (sección 4,
   Exportar).

Detalles en `grc\README.md` y `grc\FORMATO.md`.

## 3. Desde la línea de órdenes

```bat
.venv\Scripts\python -m app                         :: la aplicación
.venv\Scripts\python -m app --tema oscuro
cd experiments && ..\.venv\Scripts\python run_all.py :: toda la campaña (~20 min)
.venv\Scripts\python -m pytest -q tests              :: 39 pruebas (~1 min)
.venv\Scripts\python grc\generar_corrida.py --escenario C --ebn0 14
```

## 4. Qué hay en cada carpeta

| Carpeta | Contenido |
|---|---|
| `src\comm2` | el simulador: transmisor, canal, receptor, ecualizadores |
| `app` | la aplicación de escritorio |
| `experiments` | la campaña de experimentos que genera `results` |
| `results` | tablas (`data`) y figuras (`figures`) ya generadas |
| `grc` | validación con GNU Radio |
| `docs` | documentación y revisiones frente al libro |
| `presentacion` | la presentación |
| `tests` | pruebas automáticas |

No incluye el libro de Medina en PDF (pesa 124 MB) ni el entorno `.venv`, que
se crea al instalar.
