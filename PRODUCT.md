# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop

<!-- No es web/ios/android/adaptive: es una aplicacion de escritorio Qt (PySide6)
     que se abre con doble clic. El usuario rechazo explicitamente cualquier cosa
     que requiera "entrar por IP" a un servidor local. -->

## Stack

delegated: PySide6 6.11 + pyqtgraph 0.14 sobre el paquete `comm2` ya existente.
Elegido porque (a) es el unico stack de Python que redibuja constelacion y ojo a
velocidad interactiva sin pelear, (b) es el mismo linaje Qt de los *QT GUI sinks*
de GNU Radio, lo que hace coherente la validacion cruzada de la Seccion 11, y
(c) produce un ejecutable de escritorio, no un servidor web.

## Users

Dos usuarios, una sola sesion:

- **El estudiante (Luis Rey Gonzalez)** durante la defensa: conduce la aplicacion
  en vivo delante del jurado. Necesita llegar a cualquier evidencia en un gesto,
  sin tipear parametros ni esperar.
- **El Prof. Dr. Ing. Carlos A. Medina C.** evaluando el Proyecto 1: mira la
  pantalla y decide si el estudiante entiende la fisica. Puede pedir "y si subes
  el multipath?" y esperar ver la respuesta al instante.

Situacion: aula o despacho, laptop, probablemente proyector, sesion corta.

## Product Purpose

Cubrir el entregable (g) de la guia —*demostracion de funcionamiento mediante
software*— y apoyar la presentacion oral (10% de la nota), convirtiendo una
biblioteca de simulacion en un instrumento que se conduce.

Exito = el profesor puede *ver* por que el receptor funciona, no solo leer que
funciona. La BER es un numero; la interfaz tiene que mostrar la fisica que
produce ese numero.

## Positioning

El proyecto ya responde a la pregunta central de la guia con datos. Lo que
ningun otro equipo va a tener es **el camino de la senal como navegacion**: la
cadena TX -> canal -> RX es la barra de navegacion, y al seleccionar una etapa
los instrumentos muestran la senal *en ese punto de derivacion*. La degradacion
y su compensacion se ven ocurrir etapa por etapa, en vez de compararse entre dos
figuras estaticas de un PDF.

Esto es posible por un hecho medido, no por una decision estetica: una corrida
completa de `run_link()` tarda 0,177 s con 4000 simbolos. El enlace entero se
puede recalcular mientras el usuario arrastra un control.

## Operating Context

- Se abre con doble clic desde un acceso directo o un `.bat`; no hay navegador,
  no hay URL, no hay servidor que arrancar a mano.
- Dos entornos de Python separados y deliberadamente aislados:
  `.venv` (Python 3.11.0) para el simulador, y `C:\Users\Luisr\radioconda`
  (Python 3.11.7, GNU Radio 3.10.9.2) para GNU Radio. Se comunican por ficheros
  `complex64`, nunca por import.
- La defensa es cronometrada: cualquier accion que tarde mas de un segundo sin
  avisar cuesta credibilidad.

## Capabilities and Constraints

Confirmado y disponible en `src/comm2/`:

- `run_link(p, chan, rxcfg)` devuelve la senal en cada punto de derivacion:
  `tx_signal`, `rx_signal`, `mf_out`, `sym_stream`, `sym_pre_eq`,
  `sym_post_eq`, `payload_rx` — exactamente los puntos que la cadena necesita.
- `stats` trae ber, ser, evm_pct, mse, eq_mse_db, eq_conv, eq_flops,
  eta_bps_hz, snr_evm_db, cfo_residual_hz y los intervalos de confianza.
- `sync_info` trae la curva de correlacion fina, el error del TED de Gardner,
  la fase del PLL, la traza `mu_track` y las estimaciones de CFO.
- `eq.learning_curve`, `eq.w`, `eq.flops_per_symbol` para convergencia y coste.
- Escenarios A/B/C/D; perfiles flat/mild/moderate/severe; ecualizadores
  none/lms/rls/zf/mmse/cma; modulaciones bpsk/qpsk/8psk/16qam/64qam.
- `metrics` ya calcula PSD, ojo, apertura de ojo y eficiencia espectral.

Restricciones:

- La simulacion NO puede correr en el hilo de la GUI: 0,177 s congelaria
  cualquier arrastre de control. Requiere hilo trabajador con descarte de
  peticiones obsoletas.
- GNU Radio no es importable desde `.venv`. Toda interaccion con el es por
  subproceso contra el interprete de radioconda.
- 64-QAM no alcanza BER 1e-3 en escenario C con este receptor. Es un resultado
  medido, no un fallo; la interfaz no debe presentarlo como error.

## Brand Commitments

- Idioma: espanol, con la terminologia tecnica exacta que ya usa el repositorio
  y el informe LaTeX (ecualizador, apertura del ojo, factor de olvido, deriva de
  reloj, taps).
- El proyecto se titula *Receptor digital adaptativo sobre canal inalambrico
  simulado* — Proyecto 1, Comunicaciones II 2026.
- Las unidades y convenciones del informe mandan: Eb/N0 en dB, CFO como fraccion
  de Rs, retardos en tiempos de simbolo T.

## Evidence on Hand

Real, generado y versionado — nada aqui es inventado:

- `results/data/*.csv` — 15 tablas de las campanas de los 6 experimentos.
- `results/figures/*.png` y `latex/figures/*.png` — 13 figuras del informe.
- `results/RESUMEN.md` — tablas de resultados consolidadas.
- `latex/main.pdf` — el informe tecnico compilado.
- `grc/validacion_gnuradio.grc` — flowgraph de GNU Radio 3.10 (transmisor,
  canal y receptor), ejecutado y comparado con Python por
  `grc/validar_gnuradio.py`; resultados en `grc/README.md`.
- `grc/corridas/ejemplo/` — corrida de intercambio Python ↔ GNU Radio
  (formato en `grc/FORMATO.md`).
- `docs/arquitectura.md`, `docs/parametros.md`, `docs/referencias.md`.

Lo que NO existe y no debe fabricarse: la capa de analisis factorial (DOE/ANOVA/
Sobol) que se discutio como diferenciador. No hay `pyDOE3`, `statsmodels` ni
`SALib` instalados y no hay resultados factoriales en `results/`.

## Product Principles

1. **La fisica se muestra, no se afirma.** Todo numero en pantalla debe tener al
   lado la senal que lo produce.
2. **El punto de derivacion es la idea.** Ver la misma senal antes y despues de
   una etapa es lo que ensena; la aplicacion se organiza alrededor de eso.
3. **Responder mientras se arrastra.** Si el usuario tiene que pulsar "Simular"
   y esperar, la exploracion muere y vuelve a ser un PDF.
4. **Nunca mentir sobre lo medido.** Un caso que no converge se muestra como no
   convergido, con su razon. El proyecto ya tiene resultados negativos honestos
   (64-QAM en escenario C) y son parte del argumento.
5. **Dos entornos, un puente de ficheros.** La separacion `.venv` / radioconda
   es deliberada; la interfaz la respeta en vez de esconderla.

## Accessibility & Inclusion

- Proyector en aula iluminada: el contraste no puede depender de matices sutiles.
  Trazas y texto deben sobrevivir a un canon mal calibrado.
- Ningun estado se codifica solo por color: convergido / no convergido tambien
  se distingue por forma o etiqueta, porque las trazas de senal ya consumen el
  presupuesto cromatico.
