# Validación cruzada con GNU Radio

Sección 11 de la guía: *«cada equipo deberá seleccionar un experimento
representativo y reproducirlo utilizando la segunda herramienta (GNU Radio). Se
deberá analizar si ambos resultados son consistentes.»*

Esta carpeta va **aparte de la aplicación**: no la necesita ni la toca. Las dos
partes se comunican por una carpeta de ficheros, la **corrida**.

```
 aplicación (Exportar → JSON)  ─┐
                                ├─►  corrida/  ──►  validacion_gnuradio.grc  ──►  comparacion/
 grc/generar_corrida.py        ─┘    parametros.txt     (GNU Radio)               tabla + figura
                                     + señales .cf32
```

## Uso rápido

| Quiero… | Hago… |
|---|---|
| Validar la corrida de ejemplo | doble clic en `Validar GNU Radio.bat` |
| Validar lo que exportó la aplicación | arrastrar el `.json` encima de `Validar GNU Radio.bat` |
| Ver el flowgraph y ejecutarlo con sus gráficas | doble clic en `Abrir en GNU Radio.bat`, después **F6** y elegir un `parametros.txt` |
| Una corrida nueva sin la aplicación | `.venv\Scripts\python grc\generar_corrida.py --escenario B --ebn0 12 --perfil severe` |

La tabla y la figura quedan en `<corrida>\comparacion\` (`tabla.txt`,
`tabla.csv`, `validacion.png`). Lo que escribe GNU Radio queda en
`<corrida>\gnuradio\`.

## Ficheros

| Fichero | Lo ejecuta | Qué hace |
|---|---|---|
| `validacion_gnuradio.grc` | GNU Radio | el flowgraph: transmisor + canal + receptor, con tres pestañas de gráficas |
| `corrida.py` | `.venv` | formato de la corrida: escribir (`escribir_corrida`) y leer |
| `generar_corrida.py` | `.venv` | simula un enlace y escribe la corrida; acepta el JSON de la aplicación |
| `validar_gnuradio.py` | `.venv` | compila y ejecuta el flowgraph sin ventanas y compara |
| `ejecutar_flowgraph.py` | radioconda | lo lanza `validar_gnuradio.py`; ejecuta el flowgraph hasta que se acaban los ficheros |
| `FORMATO.md` | — | el formato de la corrida, para quien la genere |
| `corridas/ejemplo/` | — | corrida de ejemplo (escenario B, canal moderado, QPSK, 12 dB) |

Hay **dos intérpretes de Python** y no se mezclan: `.venv` para el proyecto y
el de radioconda para GNU Radio (`import gnuradio` desde `.venv` no puede
funcionar). Se comunican solo por ficheros.

## El flowgraph, bloque a bloque

Al abrirlo en Companion se ve organizado en **cinco franjas horizontales**,
cada una encabezada por un bloque **Note** con su título y, debajo, la
explicación:

| Franja | Qué contiene |
|---|---|
| **0 · Configuración** | los parámetros, el lector, `P` y todas las variables, agrupadas por columnas: transmisor, canal y receptor |
| **1 · Transmisor** | símbolos de Python → RRC → `grc_tx.cf32` |
| **2 · Canal** | fase fija → Channel Model → `grc_rx.cf32` |
| **3 · Receptor** | señal recibida de Python → sincronismo → ecualizador → fase → `grc_simbolos_rx.cf32` |
| **4 · Comparación** | las gráficas, GNU Radio frente a Python, cada una con sus dos fuentes |

Las franjas se conectan con **Virtual Sink / Virtual Source** (`tx_grc`,
`rx_grc`) en lugar de con cables largos que se cruzan. Para seguir una señal
de una franja a otra, busca el mismo *Stream ID*.

Las variables salen todas del `parametros.txt` a través del bloque **Python
Module `lector`** (doble clic para ver su código):
`P = lector.leer(lector.ruta(parametros))` y después
`samp_rate = float(P['fs'])`, `ch_taps = P['taps_canal']`, etc. Al editar,
Companion muestra los valores de la corrida de ejemplo.

**Cargar otra corrida desde GNU Radio:** al ejecutar (F6) se abre un diálogo
para elegir el `parametros.txt`. También se puede escribir la ruta en el bloque
`parametros`, o pasarla por línea de órdenes (`--parametros ruta`).

### 1 · Transmisor (pestaña «1 · Transmisor»)

| Bloque | Qué hace | Equivale en `comm2` |
|---|---|---|
| File Source `fuente_simbolos` | lee los símbolos de Python (preámbulo ZC, entrenamiento, datos y guarda) | `frame.build_frame` + `add_guard` |
| Throttle `ritmo_tx` | frena la reproducción para poder verla (`ritmo`) | — |
| Interpolating FIR Filter `filtro_rrc` | interpola por `sps` y filtra con el RRC | `pulse.pulse_shape` |
| QT GUI Frequency Sink / Time Sink | GNU Radio (azul) y Python (rojo) superpuestos | — |

El RRC sale de `firdes.root_raised_cosine` (el de GNU Radio), con
`span·sps+1` coeficientes y reescalado a **energía 1**: firdes normaliza a
ganancia 1 en continua y Python a energía 1. Sin ese reescalado la potencia no
coincide y el mismo `noise_voltage` significaría otra Eb/N0.

### 2 · Canal (pestaña «2 · Canal»)

| Bloque | Qué hace | Equivale en `comm2` |
|---|---|---|
| Multiply Const `fase_canal` | fase fija | `channel.apply_cfo(phase0=…)` |
| Channel Model `canal` | multitrayecto (`ch_taps`), CFO (`f_off`), reloj (`epsilon`) y AWGN (`noise_v`) | `channel.apply_channel` |

`noise_voltage` es la **desviación típica** del ruido complejo (potencia = v²):
`v = √(1/(k·Eb/N0))`. El retardo fraccional fijo y el desvanecimiento Rayleigh
no se reproducen (el lector avisa si la corrida los trae).

### 3 · Receptor (pestaña «3 · Receptor»)

Procesa **la misma señal recibida que el receptor de Python**
(`senal_rx.cf32`), así que cualquier diferencia es del receptor.

| Bloque | Qué hace | Equivale en `comm2` |
|---|---|---|
| Stream Mux `con_relleno` + Null Source | añade ceros al final (ver abajo) | — |
| Embedded Python Block `cfo_grueso` (Schmidl-Cox) | estima el CFO con el preámbulo [ZC ZC] y gira toda la señal en sentido contrario | `sync.schmidl_cox` + `sync.derotate` |
| Polyphase Clock Sync `sincronismo` | filtro adaptado + recuperación de temporización | `pulse.matched_filter` + `sync.gardner_timing_recovery` |
| Correlation Estimator `busca_trama` | busca el entrenamiento y marca su inicio con la etiqueta `corr_est` | `sync.fine_frame_sync` |
| Linear Equalizer `ecualizador` + Adaptive Algorithm (NLMS) | se entrena con la secuencia conocida y luego sigue dirigido por decisión | `equalizers` (LMS normalizado) |
| Costas Loop `lazo_fase` | fase residual, **después** del ecualizador como en Python | `sync.dd_phase_pll` |

Detalles que costaron una prueba cada uno:

- **El Correlation Estimator retrasa su salida** tanto como la secuencia que
  busca (512 símbolos). Sin los ceros del final, los últimos 512 símbolos se
  quedan dentro y se pierde parte de la carga útil.
- **Su umbral absoluto depende de la amplitud.** Por eso el filtro adaptado del
  Polyphase Clock Sync se escala a energía 1 por rama: con la normalización de
  firdes la amplitud quedaba en ~0,22 y el umbral no se alcanzaba nunca.
- **La etiqueta va en `marca = 1 + eq_taps//2`.** El estimador marca un
  símbolo antes del inicio real. Además, el ecualizador de GNU Radio es causal:
  si se le dice que el entrenamiento empieza justo donde empieza, no puede
  corregir los ecos que llegan *antes* del principal. Marcando medio ecualizador
  más tarde, su tap de referencia queda en el centro, como `ref_tap` en Python.
  Con la marca en el inicio exacto, la BER en canal severo era 0,20; centrada,
  sin errores.
- **Schmidl-Cox es un bloque propio** (doble clic en `cfo_grueso` para ver el
  código). GNU Radio no trae ninguno equivalente. Se probó el FLL Band-Edge:
  arreglaba el CFO pero lo sesga la propia ISI (el multitrayecto deforma los
  bordes de la banda) y empeoraba el canal severo y 16-QAM. El bloque retiene
  el principio de la ráfaga, estima sobre el filtro adaptado y luego deja pasar
  todo girado. Medido: 379,3 Hz estimados para 375 Hz reales.
- **El paso del NLMS es 0,2, no el `eq_mu` de Python** (0,5): las dos
  normalizaciones no coinciden. Se eligió midiendo seis corridas. Con 0,1 la
  QPSK iba bien pero 16-QAM fallaba (992/16000 errores): el ecualizador no
  seguía el giro residual. Con 0,2 todas coinciden con Python.
- **GNU Radio 3.9 eliminó `lms_dd_equalizer_cc` y `cma_equalizer_cc`.** Hoy son
  `variable_adaptive_algorithm` (lms, nlms, cma) + `digital_linear_equalizer`.
  Los tutoriales de 3.7/3.8 usan los bloques antiguos.

## Resultados medidos (GNU Radio 3.10.9.2)

Corrida de ejemplo, escenario B, canal moderado, QPSK, Eb/N0 = 12 dB:

| Etapa | Magnitud | Python | GNU Radio |
|---|---|---|---|
| Transmisor | diferencia muestra a muestra | — | **−142,9 dB** |
| Transmisor | ancho de banda 99 % | 145,51 kHz | 145,51 kHz |
| Transmisor | PAPR | 3,93 dB | 3,93 dB |
| Canal | potencia recibida | 0,1305 | 0,1309 (+0,4 %) |
| Receptor | BER | 6,25·10⁻⁴ (5/8000) | 5,0·10⁻⁴ (4/8000) |
| Receptor | EVM | 30,8 % | 31,6 % |

−143 dB es el redondeo de `float32`: **el transmisor de GNU Radio produce la
misma forma de onda que el de Python**, muestra a muestra.

En otros escenarios (mismo flowgraph, sin retocar nada). «Antes» es la
versión sin Schmidl-Cox y con NLMS 0,1:

| Corrida | BER Python | GNU Radio antes | GNU Radio ahora | EVM Python / GNU Radio |
|---|---|---|---|---|
| B, severo, QPSK, 14 dB | 1/8000 | 0/8000 | 0/8000 | 19,5 / 19,7 % |
| **C, moderado, QPSK, 14 dB** (CFO 375 Hz, fase 37°, 20 ppm) | 0/8000 | **no engancha** | **0/8000** | 24,9 / 25,5 % |
| **B, moderado, 16-QAM, 18 dB** | 0/16000 | **992/16000** | **6/16000** | 11,6 / 12,5 % |
| A, plano, QPSK, 8 dB | 1/8000 | 20/8000 | 9/8000 | 29,7 / 32,2 % |
| B, h = 0,0.2,1,0,0.8, QPSK, 12 dB | 22/8000 | 67/8000 | 41/8000 | 36,8 / 38,9 % |

En todas, los intervalos de confianza del 95 % de las dos BER se solapan
(`validar_gnuradio.py`). Las dos últimas siguen algo por detrás (2 a 2,5 puntos
de EVM). NO VERIFICADO: lo más probable es el ruido de desajuste del
ecualizador, porque Python reduce el paso a la cuarta parte al pasar a
dirigido por decisión (`dd_mu_scale`) y el NLMS de GNU Radio no lo hace.

El experimento de referencia para la validación sigue siendo el **escenario
B con QPSK** (Experimento 2, efecto de la ISI), pero ya no es el único en el
que coinciden.

## Lo que no hace

- No reproduce Rayleigh ni el retardo fraccional fijo del canal.
- Schmidl-Cox trabaja sobre la primera ráfaga: no está pensado para un flujo
  continuo de ráfagas, sino para una corrida.
- No hay codificación de canal (tampoco en Python).
