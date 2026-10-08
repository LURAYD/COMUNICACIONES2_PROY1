# ¿Se aplica bien en el proyecto la teoría del libro de Medina?

Libro: C. A. Medina C., *Fundamentos de Ingeniería de Comunicación*, Parte 2
(capítulos 9 a 15). «pdf N» es la página del fichero; «lib N», la página
impresa.

**Fecha:** 4 de octubre de 2026.

## Cómo se comprobó

1. **Lectura.** El PDF son 259 páginas escaneadas sin capa de texto; se leyó
   como imagen. Capítulos 9 y 12 y la sección 10.7, página a página; el resto
   del 10 y el 11, solo lo que toca al proyecto; 13 a 15 (teoría de la
   información y codificación) **no leídos**, porque el proyecto no tiene
   codificación. Toda ecuación citada aquí se verificó con la página delante.
2. **Medición.** Leer el código y ver que «la fórmula es la misma» no prueba
   que la teoría se aplique bien. Por eso cada punto central se **ejecutó**:
   se corrió el enlace del proyecto y se comparó el número que sale con el que
   predice la ecuación del libro. Lo marcado **VERIFICADO** es de esta sesión,
   en esta máquina. Parámetros: `fs` 1 MHz, 8 muestras por símbolo, β = 0,35,
   `span` 10, tramas de 20 000 símbolos.

Veredictos: **Bien** (la teoría se aplica y el número sale), **Con matiz**
(se aplica, pero con una diferencia que hay que declarar), **Mal** (la teoría
dice una cosa y el proyecto hace o dibuja otra), **No está** (el libro lo trae
y el proyecto no).

---

## 1. Resumen

| # | Teoría del libro | Dónde se aplica | Veredicto |
|---|---|---|---|
| 1 | Criterio de Nyquist y coseno alzado (9.13), (9.19) | `pulse.py` | Bien, con 2 % de ISI propia por truncar |
| 2 | Reparto en raíz de coseno alzado (9.23)–(9.25) | `pulse.rrc_filter` en Tx y Rx | Bien |
| 3 | Ancho de banda `B0(1+α)` (9.21) | `params.bw` | Bien; convenio distinto |
| 4 | Filtro acoplado (12.14), (12.25)–(12.27) | `pulse.matched_filter` | Bien |
| 5 | Eb/N0, varianza del ruido (12.2), (12.3), (12.10) | `channel.noise_sigma2` | Bien |
| 6 | BER y SER de QPSK, M-PSK, M-QAM (12.96)–(12.103) | `modulation.ber_theory` y enlace completo | Bien; pérdida de implementación de 0,1 a 0,4 dB |
| 7 | Gray: `Pb ≈ Ps/k` (12.119) | `modulation.py` | Bien |
| 8 | ISI como cursor más interferencia (9.11) | `metrics.isi_metrics`, vista de ISI | Bien |
| 9 | Distorsión de pico y ojo cerrado (lib 287) | `isi_metrics`, experimento 7 | Bien |
| 10 | Diagrama de ojo y sus cuatro parámetros (lib 281–282) | `metrics.eye_*`, `app/displays.py` | Con matiz: mide dos de cuatro |
| 11 | Ecualizador MMSE (9.36)–(9.38) | `equalizers.design_mmse` | Bien la fórmula; **mal el canal con que se alimenta** |
| 12 | Ecualizador ZF (9.35)–(9.36) | `equalizers.design_zf` | Con matiz: es otro ZF; mismo problema de canal |
| 13 | ZF ≈ MMSE sin ruido, MMSE mejor con ruido (Ej. 9.7) | Experimento 3 | Bien la tendencia |
| 14 | Estimar el canal con secuencia de entrenamiento (lib 285) | `frame.pn_qpsk`, LMS y RLS | Bien en los adaptativos; **no se usa** en ZF/MMSE |
| 15 | Espaciado fraccional, τ = T/2 (lib 284–285) | Ecualizador a una muestra por símbolo | No está |
| 16 | Constelaciones QPSK, M-PSK, 16-QAM (10.27), (10.30), Fig. 10.35 | `modulation.py` | Bien; etiquetado de bits distinto |
| 17 | Ambigüedad de fase y preámbulo conocido (lib 321) | `link.coarse_gain_phase`, PLL | Bien |
| 18 | Multitrayecto y canal selectivo (lib 335–337) | `channel.MultipathProfile` | Bien |
| 19 | Límite de Shannon en el plano Eb/N0–eficiencia (12.123) | `exp5_modulacion.py` | **Mal**: se dibuja otra curva |

---

## 2. Lo que se aplica bien, con la evidencia

### 2.1 Pulsos: Nyquist, coseno alzado, RRC (lib 274–280)

**Teoría.** Sin ISI si el pulso total vale cero en todos los instantes de
muestreo menos uno (9.13). El coseno alzado (9.19) lo cumple; se reparte en
dos raíces, una en cada extremo (9.23)–(9.25).

**En el proyecto.** `rrc_filter` en transmisor y receptor; `rc_filter` es la
(9.19) literal.

**VERIFICADO.** La cascada RRC∗RRC del proyecto frente a la (9.19) del libro:

| β | `span` | Derivaciones | Diferencia máxima con (9.19) | ISI propia (distorsión de pico) |
|---|---|---|---|---|
| 0,35 | 10 (el del sistema) | 81 | 0,0058 | **0,0204** |
| 0,35 | 20 | 161 | 0,0019 | 0,0075 |
| 1,00 | 10 | 81 | 0,0010 | 0,0018 |

La teoría se cumple. El 2 % de ISI propia es el efecto de truncar que el libro
describe en la Fig. 9.9 (48 frente a 128 derivaciones). En potencia son
−41 dB: irrelevante para QPSK, parte del suelo de 64-QAM. Nota:
`excess_bandwidth_check` informa 0,0075 porque usa `span=20`, no el del
sistema.

### 2.2 Ancho de banda (lib 278, 280)

**VERIFICADO.** Potencia transmitida dentro de `Rs(1+β)`:

| β | `Rs(1+β)` | Potencia dentro | Ancho del 99 % medido | PAPR |
|---|---|---|---|---|
| 0,20 | 150,00 kHz | 99,976 % | 133,79 kHz | 5,44 dB |
| 0,35 | 168,75 kHz | 99,992 % | 145,51 kHz | 3,97 dB |
| 0,50 | 187,50 kHz | 99,997 % | 158,20 kHz | 3,27 dB |

Se cumple (9.21). Dos cosas que declarar al citar: el libro da el ancho en
banda base, `Rs(1+α)/2`, y el proyecto el ocupado en RF, que es el doble; y los
145,51 kHz de la validación con GNU Radio son el ancho del 99 %, no el `B_T`
del libro. La PAPR baja al subir β, que es el compromiso que el libro comenta
al elegir el factor de caída.

### 2.3 Filtro acoplado y ruido (lib 379–384)

**Teoría.** El filtro que maximiza la SNR en el instante de muestreo es el
pulso invertido en el tiempo (12.14). Con RRC en ambos extremos la muestra es
`Y_k = A·b_k + N_k`, sin ISI (12.27).

**VERIFICADO**, transmisor del proyecto + AWGN + `matched_filter`:

| Eb/N0 | Ganancia de señal | Varianza de ruido medida | Teórica `1/(k·Eb/N0)` | SNR medida | Es/N0 | Con filtro no acoplado |
|---|---|---|---|---|---|---|
| 4 dB | 0,9989 | 0,19939 | 0,19905 | 6,99 dB | 7,01 dB | 6,10 dB |
| 8 dB | 0,9994 | 0,07950 | 0,07924 | 10,99 dB | 11,01 dB | 9,86 dB |
| 12 dB | 1,0003 | 0,03168 | 0,03155 | 14,99 dB | 15,01 dB | 13,34 dB |

La SNR a la salida es Es/N0 con 0,02 dB de diferencia: el filtro acoplado
funciona como dice el libro y la normalización `Σh² = 1` del proyecto equivale
a la `∫h² = T` del libro. La última columna (un promediador rectangular en
lugar del RRC) pierde entre 0,9 y 1,7 dB: es la ganancia que el libro atribuye
al filtro acoplado.

### 2.4 Probabilidad de error (lib 396–407)

**VERIFICADO**, enlace **completo** del proyecto (con sincronismo de trama,
Gardner y PLL), escenario A, 6 tramas por punto:

| Modulación | Eb/N0 | BER medida | BER del libro | Medida / libro | SER / BER medida |
|---|---|---|---|---|---|
| QPSK | 4 dB | 1,36·10⁻² | 1,25·10⁻² (12.96) | 1,09 | 1,99 |
| QPSK | 8 dB | 2,50·10⁻⁴ | 1,91·10⁻⁴ | 1,31 | 2,00 |
| QPSK | 10 dB | 4,2·10⁻⁶ | 3,9·10⁻⁶ | 1,08 | 2,00 |
| 8PSK | 8 dB | 6,65·10⁻³ | 6,18·10⁻³ (12.100) | 1,08 | 3,00 |
| 8PSK | 12 dB | 7,5·10⁻⁵ | 6,3·10⁻⁵ | 1,18 | 3,00 |
| 16-QAM | 8 dB | 1,01·10⁻² | 9,25·10⁻³ (12.103) | 1,09 | 3,95 |
| 16-QAM | 12 dB | 2,23·10⁻⁴ | 1,39·10⁻⁴ | 1,61 | 4,00 |
| 64-QAM | 14 dB | 2,82·10⁻³ | 2,15·10⁻³ | 1,31 | 5,97 |

- La BER medida está siempre algo por encima de la del libro: entre un 8 % y
  un 60 %, es decir, de 0,1 a 0,4 dB. Es lo esperable: el libro supone
  sincronismo perfecto y el proyecto lo recupera.
- `SER/BER = k` casi exacto: la aproximación de Gray (12.119) se cumple.
- QPSK tiene la misma BER que BPSK por bit, como dice (12.96).
- Aviso de cita: la Tabla 12.1 (lib 408) escribe `Q(2Eb/N0)` sin la raíz. Es
  errata; las ecuaciones numeradas sí la llevan.

**Caso aparte, BPSK a 4 dB.** Cinco tramas dieron entre 1,3 y 1,7·10⁻² (libro:
1,25·10⁻²) y una de seis dio 0,169 sin que el receptor avisara de pérdida de
enganche. Es un deslizamiento del PLL con Es/N0 = 4 dB. BPSK no es modulación
objetivo del proyecto y con QPSK a la misma Es/N0 no ocurrió en cuatro tramas.

### 2.5 ISI: cursor, distorsión de pico y ojo (lib 273–274, 281–287)

**Teoría.** La muestra es el símbolo propio más la suma ponderada de los
vecinos (9.11). La distorsión de pico es `1 − apertura del ojo`; con D = 1 el
ojo está cerrado (lib 287). Hay «razón de error irreducible» aunque no haya
ruido (lib 272).

**VERIFICADO.** Los canales de los ejemplos del libro se pasaron por el enlace
del proyecto (escenario B, 60 dB, sin ecualizar) y se midió el canal que ve el
receptor:

| Canal | D teórica | D medida | Ojo teórico `1−D` | Ojo medido | BER sin ruido |
|---|---|---|---|---|---|
| Plano | 0 | 0,026 | 1,000 | 0,952 | sin errores |
| Ej. 9.4: `0.15,−0.2,0.9,0.35,−0.1` | 0,889 | 0,897 | 0,111 | 0,073 | sin errores |
| Ej. 9.5: `0.15,0.8,−0.3,0.1` | 0,687 | 0,709 | 0,313 | 0,246 | sin errores |
| Ej. 9.7: `−0.2,0.15,0.8,−0.3,−0.15` | 1,000 | 0,985 | 0,000 | −0,026 | 6,3·10⁻³ |
| El del proyecto: `0,0.2,1,0,0.8` | 1,000 | 1,042 | 0,000 | −0,098 | 1,5·10⁻¹ |

La teoría se cumple punto por punto: mientras D < 1 no hay errores sin ruido;
en cuanto D llega a 1 aparece la BER irreducible que anuncia el libro. La
diferencia de 0,03 a 0,07 entre el ojo teórico y el medido es la ISI propia del
RRC truncado (2.1) más el residuo de temporización.

### 2.6 Constelaciones y fase (lib 311–325)

- QPSK en π/4, 3π/4, 5π/4, 7π/4 (10.30): igual en el proyecto.
- M-PSK en `2πi/M` (10.27): igual en el proyecto. La Fig. 10.25 y el
  Ej. 10.13 dibujan el 8-PSK girado π/8 y dicen que es lo preferido en la
  práctica; no cambia la BER.
- 16-QAM con Gray y niveles ±a, ±3a (Fig. 10.35): igual.
- Etiquetado de bits: el libro asigna π/4→10, 3π/4→00, 5π/4→01, 7π/4→11
  (Tabla 10.2); el proyecto, 00→45°, 01→135°, 11→225°, 10→315°. Los dos son
  Gray y el libro avisa de que la asignación puede cambiar. Misma BER.
- Ambigüedad de fase: el libro da tres salidas, preámbulo conocido,
  codificación diferencial o detección diferencial (lib 321). El proyecto usa
  la primera (Zadoff-Chu más entrenamiento). La trampa de `AGENTS.md` §6, «el
  PLL desliza 90° con el ojo cerrado», es esta ambigüedad reapareciendo en la
  carga útil, donde ya no hay símbolos conocidos.
- Deformaciones de la constelación (Fig. 10.23): el proyecto reproduce ruido,
  giro de fase y atenuación; **no** tiene interferente de tono ni
  desplazamiento de continua.

---

## 3. Donde la teoría no se aplica bien

### 3.1 ZF y MMSE reciben un canal que no es el que ve el ecualizador

Es el hallazgo más importante.

**Teoría.** El ecualizador se ajusta con la respuesta del canal **medida con
una secuencia de entrenamiento** (lib 285). Con el canal bien conocido, el
MMSE es el mejor ecualizador lineal y el LMS converge hacia él.

**En el proyecto.** `link.py:246` calcula el canal con un modelo,
`symbol_rate_channel(h, taps, sps)` con `phase="peak"`, y se lo pasa a
`design_zf` y `design_mmse`. No usa el entrenamiento.

**VERIFICADO**, 21 derivaciones, EVM a la salida (y BER a 12 dB):

| Canal | Eb/N0 | LMS | MMSE con el modelo actual | MMSE con modelo `cursor` | MMSE con canal medido en el entrenamiento | Límite lineal |
|---|---|---|---|---|---|---|
| Ej. 9.7 del libro | 30 dB | 4,1 % | **15,4 %** | 4,6 % | 7,1 % | 3,1 % |
| Ej. 9.7 del libro | 12 dB | 25,7 % (5,0·10⁻⁵) | **29,0 % (1,5·10⁻⁴)** | 24,7 % (2,5·10⁻⁵) | 24,8 % (2,5·10⁻⁵) | 23,1 % |
| `0,0.2,1,0,0.8` | 12 dB | 34,1 % (1,3·10⁻³) | **37,2 % (3,4·10⁻³)** | 32,2 % (8,5·10⁻⁴) | 32,4 % (8,8·10⁻⁴) | 29,1 % |
| `moderate` | 30 dB | 5,1 % | 6,0 % | **22,0 %** | 7,3 % | 3,2 % |
| `moderate` | 12 dB | 30,4 % (5,7·10⁻⁴) | 29,3 % (2,8·10⁻⁴) | **36,7 % (3,4·10⁻³)** | 29,5 % (2,8·10⁻⁴) | 23,8 % |

- Con canales espaciados a T y asimétricos, que son **los del libro**, el
  modelo `peak` describe una ISI distinta de la real y el «MMSE con canal
  conocido» sale **peor que el LMS**, lo contrario de lo que dice la teoría.
  A 30 dB deja un suelo de EVM del 15 %.
- El modelo `cursor` arregla esos canales pero falla con ecos fraccionales
  (`moderate`).
- El canal **medido con el entrenamiento**, que es el procedimiento del libro,
  funciona en los tres casos y devuelve el orden que predice la teoría:
  MMSE ≤ LMS.

Consecuencia para el informe: donde el experimento 3 u 8 compare ZF/MMSE con
LMS/RLS sobre un canal `h` escrito a mano, la desventaja de ZF/MMSE **no es
del ecualizador, es del canal con que se diseñó**. `AGENTS.md` §5 ya anotaba
el desfase de `phase="peak"`; lo nuevo es su coste medido y que estimar el
canal con el entrenamiento lo resuelve.

### 3.2 La curva de Shannon del experimento 5

**Teoría.** En el plano Eb/N0 frente a eficiencia, el límite es
`Eb/N0 = (2^η − 1)/η` (12.123), con asíntota en −1,6 dB (12.124).

**En el proyecto.** `exp5_modulacion.py:120` dibuja `log2(1 + SNR)` usando el
eje de Eb/N0 como si fuera SNR.

**VERIFICADO**, el desplazamiento es `10·log10(η)`:

| η [bit/s/Hz] | Límite correcto | Lo que se dibuja | Error |
|---|---|---|---|
| 1,48 (QPSK) | 0,82 dB | 2,53 dB | 1,7 dB |
| 2,96 (16-QAM) | 3,60 dB | 8,31 dB | 4,7 dB |
| 4,44 (64-QAM) | 6,69 dB | 13,16 dB | 6,5 dB |

La figura hace parecer las modulaciones más cerca del límite de lo que están.
El libro dice que sin codificación quedan «lejos, en la mayoría de los casos
por 4 dB o más» (lib 407); con la curva correcta el proyecto diría lo mismo.

### 3.3 El ZF del proyecto es otro ZF

**Teoría.** El ZF del libro recorta el sistema a una matriz cuadrada y fuerza
ceros exactos en ±N (9.35)–(9.36); minimiza la distorsión de pico.

**En el proyecto.** `design_zf` resuelve por mínimos cuadrados el sistema
completo; minimiza la energía de la ISI.

**VERIFICADO** con el Ej. 9.5 (`x = {0, 0.15, 0.8, −0.3, 0.1}`, tres
derivaciones):

| | Pesos | Distorsión de pico | SIR |
|---|---|---|---|
| Sin ecualizar | — | 0,6875 | 7,18 dB |
| ZF del libro, reproducido | −0,2047 / 1,0917 / 0,4350 | **0,0955** | 24,83 dB |
| `design_zf` | −0,1977 / 1,0931 / 0,4208 | 0,1058 | **25,07 dB** |
| MMSE sin ruido del libro (Ej. 9.6) | −0,1978 / 1,0942 / 0,4266 | — | — |

Los pesos del libro se reproducen exactos, así que la lectura es correcta.
`design_zf` coincide con `design_mmse` a `σ² = 0`, es decir, con el Ej. 9.6.
No es un error, pero en el informe hay que llamarlo «ZF de mínimos cuadrados».

### 3.4 El ojo: se miden dos parámetros de cuatro, y uno está mal nombrado

El libro define `D_A` (distorsión de amplitud), `M_N` (margen de ruido), `J_T`
(dispersión temporal de los cruces por cero) y `S_T` (ancho útil del ojo)
(lib 282). El proyecto mide los dos verticales. La clave `jitter_std` de
`metrics.eye_opening` es `std(|s|)/mean(|s|)`, dispersión de **amplitud**: no
es el `J_T` del libro. Además `eye_opening` agrupa por signo, así que en
16-QAM mide un solo ojo donde el libro cuenta `M − 1` (Fig. 9.14).

### 3.5 Ecualizador a espaciado de símbolo

El libro dice que con τ = T el exceso de banda se solapa y que en la práctica
se usa τ = T/2 (lib 284–285). El proyecto ecualiza a una muestra por símbolo.
Es una simplificación legítima, pero es la causa de fondo de 3.1 (la fase de
muestreo importa) y de que la potencia útil no se conserve con ecos
fraccionales (`AGENTS.md` §5: Pout/Pin 0,79 en `moderate`).

---

## 4. Tendencia del Ejemplo 9.7, reproducida

El libro compara ZF y MMSE con el canal `−0.2, 0.15, 0.8, −0.3, −0.15` y siete
derivaciones: iguales a 30 dB, MMSE mejor a 12 dB, ZF fallando a 10 dB.

**VERIFICADO**, mismo canal en el proyecto (QPSK, β = 0,35, 3 tramas):

| Derivaciones | Eb/N0 | Sin ecualizar | ZF | MMSE | LMS | RLS |
|---|---|---|---|---|---|---|
| 7 | 30 dB | 1,5·10⁻² | sin errores | sin errores | sin errores | sin errores |
| 7 | 12 dB | 3,2·10⁻² | 4,6·10⁻⁴ | 4,0·10⁻⁴ | 1,7·10⁻⁴ | 9,2·10⁻⁵ |
| 7 | 10 dB | 3,8·10⁻² | 2,5·10⁻³ | 2,1·10⁻³ | 1,2·10⁻³ | 7,7·10⁻⁴ |
| 21 | 12 dB | 3,2·10⁻² | 2,3·10⁻⁴ | 1,9·10⁻⁴ | 4,2·10⁻⁵ | 3,3·10⁻⁵ |
| 21 | 10 dB | 3,8·10⁻² | 2,1·10⁻³ | 1,5·10⁻³ | 7,6·10⁻⁴ | 5,3·10⁻⁴ |

«Sin errores» es en 120 000 bits: una cota de 8·10⁻⁶, no un cero.

La tendencia del libro se cumple: sin ruido ZF y MMSE coinciden, con ruido
gana MMSE. El ZF del proyecto no se hunde a 10 dB como en la tabla del libro
porque es el de mínimos cuadrados (3.3), más benigno. Que LMS y RLS queden por
delante es el defecto de 3.1, no una propiedad de los algoritmos.

---

## 5. Lo que el libro trae y el proyecto no

ASK, FSK, MSK, GMSK, OQPSK, π/4-QPSK, DPSK, DQPSK, APSK, OFDM; ecualizador
fraccionalmente espaciado; interferente de tono y desplazamiento de continua;
codificación de fuente y de canal (caps. 13–15).

## 6. Lo que el proyecto hace y el libro no respalda

El libro supone sincronismo perfecto en el capítulo 9 y detección coherente
ideal en el 12. No trae LMS, RLS, CMA ni el modo dirigido por decisión (se
queda en una frase, lib 285), ni Gardner, Schmidl-Cox, Zadoff-Chu, PLL, modelo
de Jakes, EVM o M2M4, ni la fórmula temporal de la RRC. Para todo eso valen
las referencias de `docs/investigacion_bibliografica.md`.

## 7. Límites de esta revisión

- Capítulos 13 a 15 no leídos; del 10 y del 11, solo lo aplicable.
- Las medidas son de pocas tramas (3 a 6 por punto): sirven para decir si la
  teoría se cumple, no para sustituir las curvas de la campaña.
- La comparación de 3.1 se hizo con una trama y una semilla por caso.
- No se ha modificado código. Los puntos 3.1, 3.2 y 3.4 son corregibles;
  ninguno está corregido.
