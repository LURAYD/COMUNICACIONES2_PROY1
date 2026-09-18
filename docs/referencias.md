# Referencias

Bibliografía usada en el diseño y en la fundamentación teórica del informe. Se
indica dónde interviene cada referencia dentro del proyecto.

---

## Ecualización adaptativa — núcleo del Experimento 3

**[1] E. Eleftheriou y D. D. Falconer**, *Comparing RLS and LMS adaptive equalizers
for nonstationary wireless channels*, IEEE Trans. Commun.
DOI: `10.1109/TCOM.1986.1096603` · <https://ieeexplore.ieee.org/document/1045204/>

Compara ecualizadores lineales FIR adaptativos basados en RLS y LMS sobre canales
inalámbricos no estacionarios, con resultados en MSE de régimen permanente y BER
media para canal Rayleigh selectivo en frecuencia. Es la referencia
metodológicamente más próxima al Experimento 3: mismas métricas, misma
comparación. Se usa para contrastar nuestro resultado de que el RLS converge en
≈ 2N iteraciones frente a las 60–500 del LMS según μ.

**[2] P. Balaban y J. Salz** *et al.*, *Equalizer adaptation algorithms for
high-speed wireless communications*, IEEE Trans. Veh. Technol.
<https://ieeexplore.ieee.org/document/501398>

Algoritmos de adaptación para DFE en entorno interior multitrayectoria, con
comparación de LMS, RLS, Kalman rápido y RLS en celosía sobre velocidad de
convergencia, SNR alcanzable, estabilidad y complejidad computacional: los cinco
criterios que pide la sección 8 de la guía. Aporta además estadísticas del número
de iteraciones necesarias para alcanzar cierta SNR con periodo de entrenamiento
fijo, que es el argumento cuantitativo para justificar la longitud del preámbulo
(Requisito 2) — ver `docs/parametros.md` §2.

**[3] *Comparative Study of ZF, LMS and RLS Adaptive Equalizers*** (acceso abierto)
<https://arxiv.org/pdf/2312.06084>

Implementa Zero-Forcing no adaptativo, LMS y RLS, evaluándolos en BER, velocidad
de convergencia y complejidad, con simulaciones Monte Carlo variando longitud de
entrenamiento, orden del canal, número de taps y condiciones de desvanecimiento.
Ese barrido es esencialmente el Experimento 4.5. Se usó como plantilla para
decidir qué variables barrer.

**[4] S. Haykin**, *Adaptive Filter Theory*, 5.ª ed., Pearson, 2014, caps. 5–10.

Referencia canónica para las deducciones del informe: gradiente estocástico del
LMS, recursión de Riccati del RLS, desajuste (*misadjustment*), condición de
estabilidad y la inestabilidad numérica del RLS por pérdida de definición positiva
de **P** — que es exactamente el fallo que motivó la simetrización
`P = (P + Pᴴ)/2` en `comm2.equalizers.run_rls`.

---

## Ecualización ciega

**[5] D. N. Godard**, *Self-recovering equalization and carrier tracking in
two-dimensional data communication systems*, IEEE Trans. Commun., vol. 28, n.º 11,
pp. 1867–1875, 1980. DOI: `10.1109/TCOM.1980.1094608`

Origen del CMA. Resuelve la ecualización adaptativa sin secuencia de
entrenamiento minimizando una clase de funciones de coste no convexas que
caracterizan la ISI con independencia de la fase de portadora y de la
constelación. Importa por dos razones en este proyecto: es el tercer método
implementado (`kind='cma'`) y explica por qué la convergencia del ecualizador no
requiere recuperación previa de portadora, lo que sustenta el orden
ecualizador → PLL de la arquitectura.

---

## Sincronización

**[6] K. H. Mueller y M. Müller**, *Timing recovery in digital synchronous data
receivers*, IEEE Trans. Commun., vol. COM-24, n.º 5, pp. 516–531, 1976.

Métodos de recuperación de temporización de convergencia rápida; partiendo de un
offset de peor caso la convergencia con datos binarios aleatorios ocurre
típicamente en 10–20 símbolos. El resultado que se usa aquí es el compromiso de
ganancia de lazo: el jitter residual es proporcional a la ganancia y el tiempo de
convergencia inversamente proporcional. Es exactamente el compromiso que mide el
Experimento 4.6 y que fija `timing_loop_bw = 0,02`.

**[7] F. M. Gardner**, *A BPSK/QPSK timing-error detector for sampled receivers*,
IEEE Trans. Commun., vol. 34, n.º 5, pp. 423–429, 1986.

TED implementado en `comm2.sync.gardner_timing_recovery`. La diferencia práctica
frente a [6] justifica la elección: Mueller-Müller trabaja con una muestra por
símbolo pero es dirigido por decisión, exige conocer la constelación y necesita
que el lazo de portadora haya convergido primero; Gardner no es dirigido por
decisión y tolera offset de frecuencia, a costa de necesitar dos muestras por
símbolo. Con offset de frecuencia simultáneo —el escenario C— Gardner es la
elección segura.

**[8] T. M. Schmidl y D. C. Cox**, *Robust frequency and timing synchronization for
OFDM*, IEEE Trans. Commun., vol. 45, n.º 12, pp. 1613–1621, 1997.
DOI: `10.1109/26.650240`

Estimador de trama y frecuencia con preámbulo de dos mitades idénticas,
implementado en `comm2.sync.schmidl_cox`. El documento de arquitectura explica la
modificación necesaria para recepción por ráfagas (normalización de
Cauchy-Schwarz).

**[9] M. Luise y R. Reggiannini**, *Carrier frequency recovery in all-digital
modems for burst-mode transmissions*, IEEE Trans. Commun., vol. 43, n.º 2/3/4,
pp. 1169–1178, 1995.

Estimador de frecuencia asistido por datos que promedia autocorrelaciones de
retardo creciente, implementado en `comm2.sync.fine_cfo_data_aided`. Se conserva
junto al estimador ML por periodograma (`fine_cfo_ml`) para la ablación del
informe.

---

## Ecualización en dominio de frecuencia y perfiles de canal

**[10] *Adaptive frequency-domain equalization and diversity combining for QPSK
over Rayleigh multipath*** · <https://ieeexplore.ieee.org/document/730448/>

Ecualizador adaptativo en dominio espacio-frecuencia con procesamiento LMS o RLS,
simulado sobre un enlace QPSK de 8 Mb/s en canal Rayleigh multitrayectoria
selectivo con ≈ 3 µs de dispersión de retardo RMS (60 símbolos de dispersión).
Se usa como referencia de literatura para justificar el orden de magnitud de los
perfiles retardo-potencia de `docs/parametros.md` §3, y como línea de continuación
si se quisiera añadir una cuarta estrategia de ecualización.

---

## Recurso de implementación

**[11] T. Collins, R. Getz, D. Pu y A. Wyglinski**, *Software-Defined Radio for
Engineers*, Analog Devices, 2018, cap. 6 (PDF gratuito)
<https://www.analog.com/media/en/training-seminars/design-handbooks/Software-Defined-Radio-for-Engineers-2018/SDR4Engineers_CH06.pdf>

Detectores de cruce por cero, Müller/Muller y Gardner con el diseño del lazo de
temporización paso a paso. Está orientado a implementación con GNU Radio, así que
es el puente natural entre las referencias [6]–[7] y el flowgraph de GRC de la
sección 11.

---

## Documentación de herramientas

- **GNU Radio 3.10** — wiki y guía de porting de módulos OOT:
  <https://wiki.gnuradio.org/index.php?title=GNU_Radio_3.10_OOT_Module_Porting_Guide>
- **Bloques usados en los flowgraphs**: `digital.constellation_modulator`,
  `channels.channel_model`, `digital.pfb_clock_sync_ccf`,
  `digital.costas_loop_cc`, `digital.lms_dd_equalizer_cc`.
