# Investigación bibliográfica — Proyecto 1

Búsqueda de artículos que respalden las decisiones de diseño del receptor, o
que estén directamente relacionados con él. Sirve de base para la
fundamentación teórica del informe (10 % de la evaluación) y para corregir
`docs/referencias.md`.

**Fecha:** 28 de septiembre de 2026.

---

## 1. Cómo se hizo

1. Se leyó la guía del proyecto (*Guía de Proyectos – Comunicaciones II 2026*,
   Proyecto 1) y se listaron las decisiones que necesitan respaldo: requisitos
   de la sección 4, modelo de canal (sección 7), ecualización (sección 8),
   experimentos (sección 9), métricas (sección 10) y validación cruzada con GNU
   Radio (sección 11).
2. Se hicieron **20 búsquedas en Consensus**, una o varias por decisión.
3. **Cada DOI se comprobó en OpenAlex o en Crossref**, las bases bibliográficas
   abiertas. No es un paso de trámite: tres DOI que se daban por conocidos
   (Qureshi, Lucky y Massey) resultaron apuntar a artículos que no tienen nada
   que ver. Los que aparecen aquí son los que devolvieron las bases.
4. El estado de acceso (libre o de pago) es el que informa OpenAlex.

---

## 2. Errores en `docs/referencias.md`

Hay que corregirlos antes de usar esas referencias en el informe.

| Ref. | Qué dice ahora | Lo correcto |
|---|---|---|
| **[1]** | E. Eleftheriou y D. D. Falconer, DOI `10.1109/TCOM.1986.1096603` | **R. Wang, N. Jindal, T. Bruns *et al.***, «Comparing RLS and LMS adaptive equalizers for nonstationary wireless channels in mobile ad hoc networks», IEEE PIMRC, 2002. DOI [`10.1109/PIMRC.2002.1045204`](https://doi.org/10.1109/PIMRC.2002.1045204). El DOI que se citaba es de otro artículo. |
| **[2]** | P. Balaban y J. Salz, IEEE Trans. Veh. Technol. | **K. R. Narayanan y L. J. Cimini**, «Equalizer adaptation algorithms for high-speed wireless communications», IEEE VTC, 1996. DOI [`10.1109/VETEC.1996.501398`](https://doi.org/10.1109/VETEC.1996.501398) |
| **[3]** | Título incompleto, sin autor | **R. Abdalla**, «Comparative Study of ZF, LMS and RLS Adaptive Equalization for alpha-mu Fading Channels», arXiv, 2023. DOI [`10.48550/arXiv.2312.06084`](https://doi.org/10.48550/arXiv.2312.06084) (acceso libre) |
| **[7]** | Sin DOI | DOI [`10.1109/TCOM.1986.1096561`](https://doi.org/10.1109/TCOM.1986.1096561) |
| **[9]** | Sin DOI | DOI [`10.1109/26.380149`](https://doi.org/10.1109/26.380149) |
| **[10]** | «Adaptive frequency-domain equalization and diversity combining for QPSK over Rayleigh multipath» | **M. V. Clark**, «Adaptive frequency-domain equalization and diversity combining for broadband wireless communications», IEEE J. Sel. Areas Commun., 1998. DOI [`10.1109/49.730448`](https://doi.org/10.1109/49.730448) |

**Afirmaciones pendientes de verificar** (hace falta leer el artículo):

- [1]: que respalda «el RLS converge en ≈ 2N iteraciones». Es una propiedad
  conocida del RLS (Haykin), pero no consta que el artículo de Wang lo diga.
- [2]: que compara LMS, RLS, Kalman rápido y RLS en celosía y que da
  estadísticas del número de iteraciones de entrenamiento.

---

## 3. Referencias nuevas, por decisión del proyecto

### 3.1 Ecualización — guía §8, experimentos 2 y 3

| Referencia | DOI | Qué respalda | Dónde en el código |
|---|---|---|---|
| S. U. H. Qureshi, «Adaptive equalization», *Proc. IEEE*, 1985 | [`10.1109/PROC.1985.13298`](https://doi.org/10.1109/PROC.1985.13298) | Tutorial de referencia: ISI, ZF frente a MMSE, amplificación del ruido, convergencia del LMS, RLS. Base teórica de toda la ecualización. | `equalizers.run_lms`, `run_rls`, `design_zf`, `design_mmse` |
| R. W. Lucky, «Automatic equalization for digital communication», *Bell Syst. Tech. J.*, 1965 | [`10.1002/j.1538-7305.1965.tb01678.x`](https://doi.org/10.1002/j.1538-7305.1965.tb01678.x) | Origen de la distorsión de pico D = Σ\|cₖ\|/\|c₀\| y del ecualizador transversal con entrenamiento. | `metrics.isi_metrics` (`peak_distortion`), experimento 7 |
| L. Davisson, «Two theorems on minimax equalization», *IEEE Trans. Inf. Theory*, 1971 | [`10.1109/TIT.1971.1054620`](https://doi.org/10.1109/TIT.1971.1054620) | Demuestra que el resultado de Lucky solo vale si la distorsión sin ecualizar es menor que 100 % (D < 1). Respalda «ojo cerrado cuando D ≥ 1». | Experimento 7, vista «ISI y ecualizador» |
| G. Ungerboeck, «Theory on the speed of convergence in adaptive equalizers…», *IBM J. Res. Dev.*, 1972 | [`10.1147/rd.166.0546`](https://doi.org/10.1147/rd.166.0546) | Velocidad de convergencia del LMS en función del número de taps, del paso y del espectro del canal. | `run_lms` (μ), métrica de convergencia del experimento 3 |
| J. Cioffi, G. Dudevoir, M. V. Eyuboglu, G. D. Forney, «MMSE decision-feedback equalizers and coding. I», *IEEE Trans. Commun.*, 1995 | [`10.1109/26.469441`](https://doi.org/10.1109/26.469441) | SNR del ecualizador MMSE sesgada y sin sesgar (SNR_U = SNR − 1). | `metrics.mmse_le_snr_db`: «límite de cualquier ecualizador lineal» (experimento 8 y vista de ISI) |
| C. A. Belfiore y J. H. Park, «Decision feedback equalization», *Proc. IEEE*, 1979 | [`10.1109/PROC.1979.11409`](https://doi.org/10.1109/PROC.1979.11409) | Criterios ZF, MMSE y mínima probabilidad de error; ventaja del DFE sobre el lineal. Justifica por qué la falta de DFE limita a 64-QAM. | AGENTS.md §8 |
| E. Eleftheriou y D. Falconer, «Tracking properties and steady-state performance of RLS adaptive filter algorithms», *IEEE Trans. ASSP*, 1986 | [`10.1109/TASSP.1986.1164950`](https://doi.org/10.1109/TASSP.1986.1164950) | Seguimiento del RLS y efecto del factor de olvido. Es el artículo con el que se confundió la ref. [1]. | `run_rls` (λ), escenario D |
| D. N. Godard, 1980 (ya es la ref. [5]) | [`10.1109/TCOM.1980.1094608`](https://doi.org/10.1109/TCOM.1980.1094608) | CMA; la convergencia no necesita recuperación de portadora, lo que justifica el orden ecualizador → PLL. | `run_cma` |

### 3.2 Sincronización — guía §4.8, escenario C

| Referencia | DOI | Qué respalda | Dónde en el código |
|---|---|---|---|
| F. Gardner, 1986 (ref. [7]) | [`10.1109/TCOM.1986.1096561`](https://doi.org/10.1109/TCOM.1986.1096561) | Detector de error de temporización con 2 muestras por símbolo, no dirigido por decisión. | `sync.gardner_timing_recovery` |
| M. Oerder, «Derivation of Gardner's timing-error detector from the maximum likelihood principle», *IEEE Trans. Commun.*, 1987 | [`10.1109/TCOM.1987.1096826`](https://doi.org/10.1109/TCOM.1987.1096826) | Deriva el detector de Gardner por máxima verosimilitud. | Ídem |
| K. H. Mueller y M. Müller, 1976 (ref. [6]) | [`10.1109/TCOM.1976.1093326`](https://doi.org/10.1109/TCOM.1976.1093326) | Alternativa con 1 muestra por símbolo, dirigida por decisión (descartada por el CFO del escenario C). | Justificación de la elección de Gardner |
| T. M. Schmidl y D. C. Cox, 1997 (ref. [8]) | [`10.1109/26.650240`](https://doi.org/10.1109/26.650240) | Preámbulo de dos mitades idénticas: trama y CFO grueso. | `sync.schmidl_cox`, `sync.max_cfo_acquisition` |
| D. Chu, «Polyphase codes with good periodic correlation properties», *IEEE Trans. Inf. Theory*, 1972 | [`10.1109/TIT.1972.1054840`](https://doi.org/10.1109/TIT.1972.1054840) | Secuencias de autocorrelación periódica ideal: la elección del preámbulo Zadoff-Chu. | `frame.zadoff_chu` |
| J. Massey, «Optimum frame synchronization», *IEEE Trans. Commun.*, 1972 | [`10.1109/TCOM.1972.1091127`](https://doi.org/10.1109/TCOM.1972.1091127) | Sincronismo de trama por correlación con una palabra conocida. | `sync.fine_frame_sync` |
| D. Rife y R. Boorstyn, «Single tone parameter estimation from discrete-time observations», *IEEE Trans. Inf. Theory*, 1974 | [`10.1109/TIT.1974.1055282`](https://doi.org/10.1109/TIT.1974.1055282) | Estimador de frecuencia por máxima verosimilitud = pico de la DFT, y su cota de Cramér-Rao. | `sync.fine_cfo_ml` |
| M. Luise y R. Reggiannini, 1995 (ref. [9]) | [`10.1109/26.380149`](https://doi.org/10.1109/26.380149) | Estimador de frecuencia asistido por datos para ráfagas. | `sync.fine_cfo_data_aided` |
| U. Mengali y M. Morelli, «Data-aided frequency estimation for burst digital transmission», *IEEE Trans. Commun.*, 1997 | [`10.1109/26.554282`](https://doi.org/10.1109/26.554282) | Estimación de frecuencia en ráfagas PSK: rango de ±20 % de Rs y precisión cerca de la cota de Cramér-Rao desde 0 dB. | Estimadores finos de CFO |
| M. Morelli y U. Mengali, «Carrier-frequency estimation for transmissions over selective channels», *IEEE Trans. Commun.*, 2000 | [`10.1109/26.870025`](https://doi.org/10.1109/26.870025) | Sobre canal selectivo hay que estimar la frecuencia **junto con** el canal. Explica lo medido: el CFO fino aplicado antes del ecualizador pasa de 2–5 Hz a 10–25 Hz de error. | Orden de bloques de `link.run_link` (AGENTS.md §4.3) |
| A. J. Viterbi y A. M. Viterbi, «Nonlinear estimation of PSK-modulated carrier phase…», *IEEE Trans. Inf. Theory*, 1983 | [`10.1109/TIT.1983.1056713`](https://doi.org/10.1109/TIT.1983.1056713) | Estimador de fase por potencia M-ésima, sin datos. | `metrics.slow_phase` (enderezado del ojo) |

### 3.3 Modelo de canal — guía §7

| Referencia | DOI | Qué respalda | Dónde en el código |
|---|---|---|---|
| D. J. Young y N. C. Beaulieu, «The generation of correlated Rayleigh random variates by inverse discrete Fourier transform», *IEEE Trans. Commun.*, 2000 | [`10.1109/26.855519`](https://doi.org/10.1109/26.855519) | Fading Rayleigh con espectro de Jakes por IDFT: el método que usa el simulador. | `channel.jakes_taps`, `apply_rayleigh` (escenario D) |
| T. Laakso, V. Välimäki, M. Karjalainen, U. K. Laine, «Splitting the unit delay», *IEEE Signal Process. Mag.*, 1996 | [`10.1109/79.482137`](https://doi.org/10.1109/79.482137) | Filtros de retardo fraccional por sinc con ventana. | `pulse.frac_delay_taps`, `MultipathProfile.taps` |
| M. V. Clark, 1998 (ref. [10], corregida) | [`10.1109/49.730448`](https://doi.org/10.1109/49.730448) | Orden de magnitud de la dispersión de retardo en QPSK sobre canal Rayleigh selectivo. | `docs/parametros.md` §3 |

### 3.4 BER y métricas — guía §10, experimento 1

| Referencia | DOI | Qué respalda | Dónde en el código |
|---|---|---|---|
| K. Cho y D. Yoon, «On the general BER expression of one- and two-dimensional amplitude modulations», *IEEE Trans. Commun.*, 2002 | [`10.1109/TCOMM.2002.800818`](https://doi.org/10.1109/TCOMM.2002.800818) | BER exacta de PAM y QAM con Gray en AWGN; las aproximaciones clásicas salen de sus términos dominantes. | `modulation.ber_theory`, experimento 1 (ver §6) |
| M. Jeruchim, «Techniques for estimating the bit error rate in the simulation of digital communication systems», *IEEE J. Sel. Areas Commun.*, 1984 | [`10.1109/JSAC.1984.1146031`](https://doi.org/10.1109/JSAC.1984.1146031) | Estimación de BER por Monte Carlo y su incertidumbre. Respalda la regla de no afirmar nunca BER = 0. | `metrics.ErrorRate.ci95`, `min_bits_for_ber`, `bench.fmt_ber` |
| D. Pauluzzi y N. Beaulieu, «A comparison of SNR estimation techniques for the AWGN channel», *IEEE Trans. Commun.*, 2000 | [`10.1109/26.871393`](https://doi.org/10.1109/26.871393) | Comparativa de estimadores de SNR, entre ellos M2M4. Respalda el hallazgo medido: M2M4 solo es válido a tasa de símbolo. | `metrics.estimate_snr_m2m4` |
| R. Shafik, M. S. Rahman, A. R. Islam, «On the extended relationships among EVM, BER and SNR as performance metrics», ICECE, 2006 | [`10.1109/ICECE.2006.355657`](https://doi.org/10.1109/ICECE.2006.355657) | Relación entre EVM, SNR y BER. | `metrics.evm_percent`, `evm_to_snr_db` |

### 3.5 Validación cruzada con GNU Radio — guía §11

Consensus no devuelve trabajos revisados por pares que validen un simulador
contra GNU Radio: solo trabajos docentes. El más citable es A. Wyglinski *et
al.*, «Digital Communication Systems Education via Software-Defined Radio
Experimentation», 2011 (sin DOI verificado), que usa MATLAB, Simulink, GNU
Radio y GNU Radio Companion en la enseñanza de comunicaciones digitales.

Es un hueco, y conviene decirlo en el informe: la comparación cuantitativa del
proyecto (ancho de banda ocupado +0,0 %, PAPR −1,5 %, `noise_voltage` como
desviación típica) no tiene precedente directo en la literatura encontrada.

---

## 4. Trabajo más parecido a este proyecto

- **J. Cai, «Performance Comparison of LMS and RLS Equalizers in Optical
  Communication Channels», ICCECT, 2026.** DOI
  [`10.1109/ICCECT68671.2026.11565289`](https://doi.org/10.1109/ICCECT68671.2026.11565289).
  Canal FIR de 5 taps, Monte Carlo de 0 a 16 dB, sin ecualizar frente a LMS y
  RLS: es casi el experimento 8. Sin ecualizar obtiene un suelo de BER de 0,16,
  parecido al nuestro (0,14–0,20 con h = [0, 0.2, 1, 0, 0.8]). **Pero concluye
  que el RLS es muy superior al LMS** (BER 0,0027 a 16 dB, más de un orden de
  magnitud mejor), mientras que aquí LMS y RLS quedan cerca. Hay que leerlo para
  explicar la diferencia: posibles causas son el paso del LMS, el entrenamiento
  y el modo dirigido por decisión.
- **R. Abdalla, arXiv 2023** (ref. [3]). ZF, LMS y RLS barriendo la longitud de
  entrenamiento, el orden del canal, el número de taps y el fading. De acceso
  libre.

---

## 5. PDFs que hay que conseguir

Todos son de IEEE y de pago; el único de acceso libre es el de arXiv. Por orden
de prioridad:

| # | DOI | Artículo | Para qué se necesita |
|---|---|---|---|
| 1 | [`10.1109/ICCECT68671.2026.11565289`](https://doi.org/10.1109/ICCECT68671.2026.11565289) | Cai 2026 | Comparar sus números con el experimento 8 y explicar por qué su RLS gana y el nuestro no. |
| 2 | [`10.1109/PIMRC.2002.1045204`](https://doi.org/10.1109/PIMRC.2002.1045204) | Wang *et al.* 2002 (ref. [1]) | Verificar lo que el repositorio afirma de este artículo. |
| 3 | [`10.1109/VETEC.1996.501398`](https://doi.org/10.1109/VETEC.1996.501398) | Narayanan y Cimini 1996 (ref. [2]) | Ídem para la ref. [2]. |
| 4 | [`10.1109/26.870025`](https://doi.org/10.1109/26.870025) | Morelli y Mengali 2000 | Citar con precisión el sesgo del CFO fino antes del ecualizador (orden de bloques). |
| 5 | [`10.1109/26.469441`](https://doi.org/10.1109/26.469441) | Cioffi *et al.* 1995 | Confirmar la fórmula del límite MMSE que usa `mmse_le_snr_db`. |
| 6 | [`10.1109/PROC.1985.13298`](https://doi.org/10.1109/PROC.1985.13298) | Qureshi 1985 | Base teórica de la ecualización en el informe. |
| 7 | [`10.1109/26.871393`](https://doi.org/10.1109/26.871393) | Pauluzzi y Beaulieu 2000 | Respaldar el hallazgo sobre M2M4. |
| 8 | [`10.1109/TIT.1983.1056713`](https://doi.org/10.1109/TIT.1983.1056713) | Viterbi y Viterbi 1983 | Respaldar el estimador de fase del ojo. |

Los demás son clásicos que se citan por su resultado conocido; no hace falta
leerlos para usarlos.

**Cómo pasarlos:** adjuntándolos en la conversación. **No los guardes dentro
del repositorio**: es público en GitHub y son artículos con derechos de autor.

---

## 6. Observaciones que salieron de la investigación

1. **La BER teórica de QAM no es exacta.** `modulation.ber_theory` usa solo el
   término dominante, aunque el comentario diga «exacta para el término
   dominante». Según Cho y Yoon (2002) esa aproximación se separa de la exacta
   a Eb/N0 bajo en 16 y 64-QAM. Para QPSK sí es exacta. Conviene matizar el
   comentario o implementar la expresión completa antes de presentar el
   experimento 1 con 16-QAM.
2. **LMS frente a RLS no coincide con Cai (2026).** Ver §4.
3. **La validación con GNU Radio no tiene precedente directo.** Ver §3.5.
4. **Tres DOI conocidos de memoria eran incorrectos.** Cualquier referencia
   nueva que se añada al informe debe comprobarse igual, en OpenAlex o en
   Crossref, antes de citarla.
