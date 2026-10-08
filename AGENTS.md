# AGENTS.md — contexto para agentes de IA

Documento de traspaso. No está escrito para una persona: está escrito para que
otro agente pueda trabajar en este repositorio sin re-derivar lo que ya se
midió y sin repetir los fallos que ya ocurrieron.

Convención de este fichero: **VERIFICADO** = ejecutado y observado en esta
máquina, con el número que salió. **NO VERIFICADO** = plausible pero nadie lo
ha ejecutado. **NO EXISTE** = declarado explícitamente ausente para que no se
alucine.

---

## 1. Qué es

Simulador completo de un enlace digital en banda base compleja (TX con RRC,
canal con multitrayecto + AWGN + errores de sincronismo, RX adaptativo con
LMS/RLS) más una aplicación de escritorio que lo conduce en vivo y una
validación cruzada contra GNU Radio.

Es el Proyecto 1 de Comunicaciones II 2026. Español en todo: código, comentarios,
documentación e interfaz.

**Volumen:** 8388 líneas, 38 módulos.

---

## 2. Entornos de ejecución — LEER ANTES DE TOCAR NADA

Hay **dos intérpretes de Python** y mezclarlos rompe cosas.

| Entorno | Ruta | Para qué |
|---|---|---|
| `.venv` | `C:\comunicacion\.venv\Scripts\python.exe` (3.11.0) | Simulador, experimentos, aplicación |
| radioconda | `C:\Users\Luisr\radioconda\python.exe` (3.11.7) | **Solo** GNU Radio 3.10.9.2 |

**Regla dura:** `import gnuradio` desde `.venv` **no puede funcionar**. Los
bindings están compilados contra el intérprete del sistema. No intentes
arreglarlo con `pip install`; no existe tal paquete. Toda interacción con GNU
Radio va por **subproceso** contra el intérprete de radioconda, con ficheros
`complex64` como puente. El guion puente es `app/grc_driver.py`, que solo
depende de `gnuradio` y `numpy`.

VERIFICADO: `grcc.exe` está en `radioconda\Scripts\`, `gnuradio-companion.exe`
también. La detección automática está en `app/grcview.py::detect()`.

---

## 3. Arquitectura y dirección de dependencia

```
grc/          validación cruzada (transversal)
app/          banco de pruebas de escritorio   →  usa src/comm2
experiments/  campaña de simulación            →  usa src/comm2
src/comm2/    biblioteca                       →  solo NumPy/SciPy
tests/        pruebas de propiedades           →  usa src/comm2
```

Una capa **solo** depende de las de abajo. Consecuencias que hay que preservar:

- `src/comm2` **no importa Qt**. PySide6 es dependencia opcional (`.[gui]`).
- `app/` **no reimplementa física**. Llama a `run_link()`, la misma que usan los
  experimentos. Si un agente duplica lógica de señal en `app/`, rompe la
  garantía de que la pantalla y el informe dicen lo mismo.

`src/comm2/link.py` es el único módulo que conoce a todos los demás.

---

## 4. Invariantes que no se pueden romper

### 4.1 Puntos de derivación alineados índice a índice

`app/engine.py::simulate()` extrae cinco puntos a tasa de símbolo que contienen
**los mismos símbolos de carga útil, índice a índice**:

```python
d_tr = max(int(r.sync_info["fine_start"]) + frm.preamble_len, 0)
sym_taps = {
    "tx":     ideal,
    "timing": payload_of(r.sym_stream, d_tr + n_tr),
    "preeq":  payload_of(r.sym_pre_eq, n_tr),
    "posteq": payload_of(r.eq.y, n_tr),
    "pll":    payload_of(r.sym_post_eq, n_tr),
}
```

Toda la aplicación vive de esto: el morfeo de la constelación interpola
posición a posición entre etapas. Si se rompe la alineación, la animación deja
de significar algo y nadie se entera, porque sigue dibujando.

**Cómo comprobar que sigue intacto:** correr `simulate()` en escenario C y
verificar que la EVM baja de ~77 % a ~31 % entre `preeq` y `posteq`.

### 4.2 Normalizaciones de energía

- Constelación: `E{|s|²} = 1` (`modulation.py`, última línea de
  `_qam_constellation`).
- RRC: `Σh² = 1` (`pulse.py`, `normalize="energy"`).
- Perfiles multitrayecto: `Σ|g|² = 1` (`channel.py`, `MultipathProfile.taps`).

De ahí sale `σ² = 1/(k · Eb/N0)` **independientemente del sobremuestreo**.
Cambiar cualquiera de las tres desplaza todas las curvas de BER respecto a la
teórica y el Experimento 1 deja de validar nada.

La tercera es además lo que hace honesto el Experimento 2: el canal introduce
ISI **sin cambiar la SNR media**.

### 4.3 Orden de los bloques del receptor

`src/comm2/link.py`. No es libre. En particular:

- Schmidl-Cox **antes** que la temporización (es no coherente; al revés es
  circular).
- PLL de fase **después** del ecualizador (antes queda sesgado por los términos
  cruzados de la ISI — medido: el estimador fino de CFO pasa de 2–5 Hz de error
  a 10–25 Hz si se aplica antes).

### 4.4 El tema debe fijarse antes de construir widgets

`app/theme.py::set_mode()` reescribe los globales del módulo. Hay que llamarlo
**antes** de instanciar cualquier widget.

Trampa relacionada: los argumentos por defecto de función se evalúan al
importar. Por eso `widgets.py::panel_label(text, color=None)` resuelve el color
dentro del cuerpo, no en la firma. Si un agente "simplifica" eso poniendo
`color=T.INK_FAINT` en la firma, el widget queda atado al tema activo en el
momento del import.

---

## 5. Hechos verificados — no re-derivar

| Hecho | Valor | Dónde se midió |
|---|---|---|
| Una corrida de `run_link` | **0,177 s** (4000 símbolos, esc. C, LMS) | base de toda la interactividad |
| Con curva de comparación LMS↔RLS | 0,433 s | `Request.compare=True` dispara una segunda corrida |
| EVM `preeq` → `posteq` (esc. C, 12 dB) | 77,1 % → 31,1 % | invariante 4.1 |
| Apertura del ojo en las 8 etapas (esc. C, 12 dB) | 1,000 / 0,767 / 0,090 / 0,111 / 0,116 / 0,116 / 0,484 / 0,482 | perfil del camino de la señal; medida tras quitar el giro lento de portadora (antes 0,099 / 0,105 / 0,087 / 0,467, contaminadas por el giro) |
| Ojo tras el filtro adaptado en AWGN (esc. A, 12 dB) | 0,112 con el giro residual → **0,709** sin él | el estimador grueso deja ~11 Hz: 16° en los 600 símbolos del ojo, >90° en la ventana de medida |
| GNU Radio | **3.10.9.2** (radioconda, Py 3.11.7) | `detect()` |
| `tx_qpsk_canal.grc` ejecuta | 0,15 s, 160 000 muestras | headless vía `grc_driver.py` |
| Ancho de banda ocupado 99 % | Python 145,51 kHz / GRC 145,51 kHz (**+0,0 %**) | validación cruzada |
| PAPR | Python 3,99 dB / GRC 3,92 dB (−1,5 %) | validación cruzada |
| `noise_voltage` de GNU Radio | es la **desviación típica** del ruido complejo: potencia = `v²` | medido: la potencia recibida sube 0,352 al pasar v de 0 a 0,60 |
| M2M4 sobre señal sobremuestreada | 2,98 dB — **inválido** | el estimador supone módulo constante |
| M2M4 a tasa de símbolo | 5,07 dB — válido | tras filtro adaptado y diezmado |
| Arranque de la aplicación | ventana visible en **~6 s** | `Banco de pruebas.bat` |
| Coste del ecualizador (N=21) | LMS 168 mult/símbolo, RLS 7392 (**44×**) | `equalizers.flop_count` |
| Canal `h = 0,0.2,1,0,0.8` (espaciado a T) | SIR teórica 1,68 dB / medida 1,64 dB; D = 1,000; BER@12 dB sin ecualizar 1,97·10⁻¹, LMS 1,58·10⁻³ | `exp7_isi_canal.py` |
| `Σ\|g\|²=1` con ecos fraccionales **no** conserva la potencia útil | Pout/Pin: mild 1,157, moderate 0,790, severe 1,005 | la SNR real de B/C es ~1 dB menor que la rotulada; con ecos a múltiplos de T sí es exacta |
| `symbol_rate_channel(phase="peak")` | con ecos asimétricos muestrea 1 muestra antes del instante de Nyquist (`h=1,-0.5`: D 0,646 en vez de 0,5) | ZF/MMSE lo usan así; `phase="cursor"` devuelve `h/‖h‖` exacto |

---

## 6. Trampas conocidas — ya ocurrieron

Cada una costó una sesión de depuración. Si un agente "limpia" estas líneas,
vuelven.

### En `src/comm2/` (código original, no modificado en esta sesión)

1. **Schmidl-Cox normalizado solo con `R_b`** → la métrica supera 1 en el flanco
   final de la ráfaga y aparece un máximo espurio. Se normaliza con `√(Ra·Rb)`.
2. **Correlación contra el preámbulo** → el lóbulo lateral de altura 0,5 en ±L
   (dos mitades idénticas) hace enganchar 64 símbolos tarde. Se correlaciona
   contra la secuencia de entrenamiento, que es aperiódica.
3. **NCO de Gardner sin límite** → `v` supera 1, el paso se vuelve nulo y el
   bucle `while` **no termina nunca**. Limitado a ±50 %.
4. **RLS sin simetrizar `P`** → la recursión de Riccati pierde la simetría
   hermítica por redondeo y el error se amplifica en `1/λ` por iteración hasta
   divergir. `P = 0.5*(P + P.conj().T)` en cada paso.
5. **PLL con integrador a cero** → el transitorio dura `1/(Bn·T)` = 2000
   símbolos y produce fallos catastróficos intermitentes con 16-QAM. Se siembra
   con la frecuencia estimada.

### En las medidas de ISI (sesión del canal `h`)

- **`metrics.eye_opening` agrupa por el signo *recibido*** y por tanto nunca
  baja de 0 aunque el ojo esté cerrado. Para comparar con la teoría usar
  `metrics.eye_opening_known` (agrupa por símbolo transmitido).
- **Medir ISI sobre el entrenamiento** mezcla el transitorio de Gardner:
  el peor caso en canal plano cae de 0,95 a 0,77. Medir sobre la carga útil.
- **PLL de fase con el ojo cerrado desliza 90°.** Sin ecualizar,
  `h = 0,0.2,1,0,0.8` a 6 dB dio BER 0,587 (> 0,5): no es ISI, es el PLL
  dirigido por decisión con un 20 % de decisiones erróneas. En escenario B
  (sin CFO) `exp8` apaga CFO y PLL para aislar la ISI.
- **El ruido a la entrada del ecualizador no es `sigma2/|gain_est|²`** (sale
  1,7 dB alto). Usar el residuo de `metrics.estimate_symbol_channel`.
- **La ventana de ojo de `exp2_isi.eye_window` incluye el preámbulo ZC**, cuya
  componente I recorre [−1, 1]: ensucia el ojo aun con canal plano.

### En Qt / PySide6 (código de `app/`)

6. **`QSlider:focus::handle:horizontal`** — pseudo-estado antes del subcontrol.
   Qt descarta **todo** el estilado del deslizador y la pista desaparece de la
   pantalla **sin dar ningún error**. El orden correcto es
   `QSlider::handle:horizontal:focus`.
7. **`rgba()` en QSS usa alfa 0–255, no 0–1.** Un `rgba(255,255,255,0.88)` se
   trunca a alfa 0 y la superficie queda transparente.
8. **Hoja de estilo en un contenedor se hereda a todos sus hijos.** Un
   `widget.setStyleSheet("background: transparent")` en un contenedor pinta de
   transparente también a los botones que contiene. Por eso `theme.py` no
   declara fondo global y solo las superficies con nombre lo declaran.
9. **`deleteLater()` es asíncrono.** El widget sigue pintándose hasta que el
   bucle de eventos procese el borrado. Hay que llamar a `setParent(None)`
   antes si se quiere que desaparezca ya.
10. **`EqResult.learning_curve` YA viene en dB** (ver `equalizers._analyze`).
    Aplicarle `10*log10` otra vez produce NaN y la gráfica sale vacía.

11b. **IBM Plex no trae `●`, `■`, `✕` ni subíndices como `ₖ`.** Qt los pinta
    como cajas vacías, sin error. En leyendas de texto usar bloques de color
    (`<span style='background:…'>`) o letras normales.
11c. **pyqtgraph pone prefijo SI a ejes sin unidades**: ±0,5 Rs sale como
    «±500 (x0.001)». `axis.enableAutoSIPrefix(False)` (ver `isiview._no_si`).

11d. **Un lienzo con `setLogMode(y=True)` recibe datos LINEALES.** pyqtgraph
    aplica el log10 él mismo; pasarle `log10(BER)` es un logaritmo doble
    (NaN) y no se dibuja nada, sin error. Así estuvo la vista de campaña hasta
    el 2026-09-27. Los rangos (`setYRange`) y las `InfiniteLine`, en cambio,
    van en coordenadas de la vista, es decir, en décadas.
11e. **`gnuradio-companion.exe` lanzado directamente muere al arrancar**
    (`AssertionError` en `gi/overrides`: GTK no encuentra Pango sin el entorno
    de conda activado). Hay que lanzarlo como el menú Inicio:
    `pythonw cwp.py --no-console <radioconda> gnuradio-companion.exe <.grc>`
    (ver `grcview.companion_command`). VERIFICADO: así abre
    `rx_qpsk_desde_python.grc`.
11f. **Señal de un `QThread` conectada a una función suelta** se ejecuta en el
    hilo del trabajador, no en el de la interfaz. Llamar ahí a `grab()` o
    tocar widgets cuelga. Conectar siempre a métodos de un `QObject` que viva
    en el hilo principal (conexión en cola).

11g. **Diagrama de ojo: tres fallos que se sumaban (corregidos 2026-09-27).**
    (1) Se centraba en `fase óptima + sps/2`: el instante de decisión caía en
    t = ±T/2 y en el centro quedaba el cruce. (2) Sin `connect="finite"`
    (ver 11d), las rectas de unión entre trazas cruzaban el panel. (3) El giro
    lento de portadora cerraba el ojo de la componente I sin haber ISI: ahora
    `metrics.slow_phase` lo quita antes de medir y dibujar (tras el filtro
    adaptado y en las etapas a tasa de símbolo; en «Canal» no). Las etapas a
    tasa de símbolo muestran el ojo reconstruido con el coseno alzado
    (interpolación de Nyquist), rotulado «desde los símbolos». Color de las
    trazas: `T.EYE`, rojo puro en claro y amarillo puro en oscuro (el amarillo
    sobre blanco tiene contraste 1,07:1).

### En herramientas de línea de órdenes

11. `printf '\\end{document}'` en bash: `\e` se interpreta como ESC.
12. `sed 's/\usetikzlibrary/.../'`: `\u` significa "mayúscula siguiente" en GNU
    sed y produce `\Setikzlibrary`.
13. `%` dentro de modo matemático con babel-spanish: rompe la compilación.
14. `\frontmatter` y `\mainmatter` **no existen** en la clase `report`; hay que
    usar `book`.

---

## 7. Comandos verificados

```bash
# Aplicación de escritorio
"C:\comunicacion\Banco de pruebas.bat"          # doble clic, ventana en ~6 s
.venv\Scripts\python -m app                      # equivalente
.venv\Scripts\python -m app --tema oscuro        # instrumento de fósforo

# Sin interfaz: 14 ficheros + medidas.csv, ninguna ventana
.venv\Scripts\python -m app --export salida --escenario C --ebn0 12 --eq lms

# ISI frente a un canal dado a mano (barrido de la escala de los ecos)
cd experiments && ..\.venv\Scripts\python exp7_isi_canal.py --h "0,0.2,1,0,0.8" --alfa 0:1.5:0.1
.venv\Scripts\python -m app --export salida --escenario B --perfil "0,0.2,1,0,0.8"

# Ecualizador: canal ideal frente a canal h (a mano o aleatorio con semilla)
cd experiments && ..\.venv\Scripts\python exp8_ecualizador_isi.py --semilla 7
cd experiments && ..\.venv\Scripts\python exp8_ecualizador_isi.py --h "0,0.2,1,0,0.8" --eq lms,rls

# Exportar la referencia para GNU Radio
cd experiments && ..\.venv\Scripts\python exp6_validacion_grc.py --export

# Compilar el informe del código (MiKTeX)
cd latex && pdflatex -interaction=nonstopmode informe_codigo.tex   # ×3
```

**NO VERIFICADO** (plausible, nadie lo ha ejecutado en esta sesión):
`experiments/run_all.py`, `tests/test_comm2.py`, `tests/test_campana.py`,
`exp6_validacion_grc.py` sin `--export`.

---

## 8. Lo que NO existe

Declarado explícitamente para que no se suponga implementado:

- **Capa de análisis factorial (DOE / ANOVA / Sobol).** No hay `pyDOE3`,
  `statsmodels` ni `SALib` entre las dependencias, y no hay resultados
  factoriales en `results/`. Lo que sí está es la condición para construirla:
  `Request` → `SimResult` es una función parametrizada pura.
- **Codificación de canal.** Todas las BER son sin codificar.
- **Ecualizador de decisión realimentada (DFE) ni MLSE.** Solo lineales. Ésa es
  la razón medida de que 64-QAM no alcance BER 10⁻³ en escenario C: la ISI
  residual de 21 taps es −12 dB y 64-QAM exige −20 dB.
- **No linealidad de amplificador.**
- **Ejecución sin interfaz del flowgraph de receptor.**
  `rx_qpsk_desde_python.grc` lleva sumideros Qt; solo se abre en Companion. La
  validación cruzada automática cubre transmisor y canal, no el receptor de GNU
  Radio.

---

## 9. Estado del árbol de trabajo

**Sesión del canal `h` (2026-09-25):** `src/comm2` sí se modificó, solo con
añadidos compatibles: `MultipathProfile.from_taps`, `channel.get_profile /
parse_taps / format_taps`, `metrics.isi_metrics / estimate_symbol_channel /
eye_opening_known`, `symbol_rate_channel(phase=...)` (por defecto igual que
antes) y escenarios que aceptan nombre, perfil o vector `h`. Nuevo
`experiments/exp7_isi_canal.py` (paso 7 de `run_all.py`),
`channel.random_taps` / perfil `"aleatorio:SEMILLA"` (canal reproducible:
cursor 1 en el centro, ecos uniformes en ±0,6, redondeados a 2 decimales) y
`experiments/exp8_ecualizador_isi.py` (paso 8). En la aplicación: vista
«ISI y ecualizador» (`app/isiview.py`, motor `engine.compare_isi`: 4 enlaces
ideal/h × sin/con ecualizador, escenario B sin CFO/PLL, los del canal ideal en
caché), rail con perfil «Aleatorio (semilla)» y «h escrita a mano»
(`Controls._profile_spec` → `get_profile`), y `SimController(fn=…)` para
reutilizar el hilo con descarte. `link.equalizer_breakdown` y
`metrics.mmse_le_snr_db` los comparten exp8 y la vista. Invariante 4.1
comprobado después: EVM `posteq` en escenario C = 31,1 %. Lo de abajo describe
la sesión anterior.


**Sin commit.** Todo está en el árbol de trabajo. `src/comm2/`, `tests/` y
`experiments/` **no fueron modificados** en la sesión que produjo `app/` y el
informe del código; lo verificable con `git diff --stat -- src/ tests/
experiments/` (vacío).

Añadido sin versionar: `app/`, `docs/img/`, `PRODUCT.md`, `AGENTS.md`, los dos
`.bat`, `comunicacionespng.png`.
Modificado: `README.md`, `grc/README.md`, `pyproject.toml`, `requirements.txt`.

**`latex/` está en `.gitignore`** (línea 17), de modo que `informe_codigo.tex` y
su PDF **no se versionan**. Decisión pendiente del usuario.

---

## 10. Convenciones a respetar

- **Español con tildes en todo lo visible al usuario.** Los comentarios y
  docstrings del código original usan ASCII sin tildes; los de `app/` sí las
  llevan. No unificar sin preguntar.
- **Nunca afirmar BER = 0.** Cuando no hay errores, es una cota `1/(k·N)`. El
  código lo respeta en `bench.py::fmt_ber` y en la vista de campaña, que dibuja
  esos puntos sobre una línea de suelo etiquetada.
- **Un control que no hace nada es un fallo.** Ya se corrigió dos veces: el rail
  desactivado en la vista de campaña (que sí usa sus valores) y el nivel de
  ruido fijo escondido en el panel de GNU Radio.
- **Paleta de datos validada.** Los colores de serie salen de la instancia
  documentada del método de visualización de datos, orden fijo, nunca ciclada.
  La ilustración de fondo (`app/assets/fondo.png`) manda en el chasis, pero
  **medido** no sirve como paleta categórica: sus tonos se agrupan en
  247/265/281/286 y como conjunto falla los umbrales de separación.
