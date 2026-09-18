# Arquitectura del sistema

Proyecto 1 — Comunicaciones II 2026. Documento de diseño (producto de la semana 1,
Requisito 4 de la guía). El diagrama de bloques está en
`results/figures/diagrama_bloques.png`, generado por
`experiments/exp0_diagrama_bloques.py`.

---

## 1. Convenios de simulación

Todo el sistema trabaja en **banda base compleja** (equivalente pasabajos). No se
simula portadora de RF: un offset de frecuencia de portadora se manifiesta en la
envolvente compleja como una rotación `exp(j2πf·n/fs)`, que es exactamente lo que
aplica `comm2.channel.apply_cfo`. Esto reduce la frecuencia de muestreo necesaria
en varios órdenes de magnitud sin perder ningún efecto relevante para el proyecto.

La constelación se normaliza a energía media unitaria (`E{|s|²} = 1`) y el filtro
RRC a energía unitaria (`Σh² = 1`). Con ese par de convenios, tras el filtro
adaptado y el muestreo en el instante óptimo la muestra útil vale exactamente
`a_k` y el ruido tiene varianza `σ²`, de modo que

```
Es/N0 = 1/σ²        σ² = 1 / (k · Eb/N0)
```

independientemente del sobremuestreo. Esta es la razón por la que el Experimento 1
reproduce la BER teórica sin ningún factor de ajuste empírico.

Los perfiles multitrayectoria se normalizan también a energía unitaria
(`Σ|g|² = 1`). Es una decisión deliberada: así el canal introduce **ISI y
selectividad en frecuencia sin cambiar la SNR media**, y toda la degradación
observada en el Experimento 2 es atribuible a la distorsión, no a una pérdida de
potencia.

---

## 2. Transmisor

```
bits PRBS → trama [ZC|ZC | entrenamiento | carga útil] → mapeo Gray → RRC → s(t)
```

### 2.1 Estructura de trama

| Campo | Longitud | Función |
|---|---|---|
| Preámbulo `[ZC \| ZC]` | 2 × 64 = 128 símbolos | detección de ráfaga y CFO grueso |
| Entrenamiento (PN QPSK) | 512 símbolos | adaptación del ecualizador y sincronismo fino |
| Carga útil | 8 192–20 000 símbolos | datos |
| Guarda | 64 símbolos a cada lado | evita que el transitorio del RRC contamine la ráfaga |

**Por qué Zadoff-Chu.** Es una secuencia CAZAC (envolvente constante,
autocorrelación periódica ideal). La envolvente constante evita que el detector de
ráfaga dependa del nivel instantáneo de potencia, y la autocorrelación impulsiva
da un pico nítido incluso con multitrayectoria.

**Por qué dos mitades idénticas.** Habilitan el estimador de Schmidl & Cox: la
autocorrelación con retardo `L` presenta una meseta cuya **fase** es proporcional
al offset de frecuencia. Es decir, el mismo preámbulo resuelve detección de
ráfaga y estimación de frecuencia con una sola pasada y sin conocer todavía la
temporización.

**Por qué el entrenamiento es QPSK aunque la carga útil sea 16-QAM.** Los símbolos
de módulo constante hacen que el paso normalizado del LMS y la matriz de
correlación del RLS no dependan del nivel instantáneo, lo que uniformiza la
convergencia entre modulaciones.

### 2.2 Longitud del entrenamiento

512 símbolos no es un número arbitrario. La convergencia del RLS ocupa ≈ 2N
iteraciones (42 símbolos con N = 21) y la del LMS normalizado entre 60 y 500 según
μ (medido en `exp4_5_taps_entrenamiento.csv`). 512 símbolos dejan margen para el
peor caso de μ pequeño y siguen suponiendo un coste de trama de sólo el 2,5 % con
una carga útil de 20 000 símbolos. El barrido del Experimento 4.5 muestra que
bajar de 128 símbolos degrada al LMS de forma apreciable mientras que el RLS
apenas lo nota: ésa es una de las ventajas concretas del RLS.

---

## 3. Canal

Tres escenarios obligatorios más uno adicional:

| Escenario | Contenido |
|---|---|
| **A** | AWGN únicamente. Referencia de validación. |
| **B** | Multitrayectoria FIR determinista + AWGN. Aísla el efecto de la ISI. |
| **C** | B + offset de frecuencia + offset de fase + error de temporización + deriva de reloj. |
| **D** | C con desvanecimiento Rayleigh variable en el tiempo (Doppler de Jakes). |

Los perfiles retardo-potencia y su justificación numérica están en
[`parametros.md`](parametros.md).

---

## 4. Receptor: orden de los bloques y por qué

Éste es el punto de diseño con más contenido físico del proyecto, porque el orden
de las etapas no es libre: cada una impone condiciones sobre las anteriores.

```
r(t) → RRC adaptado → Schmidl-Cox → corrección CFO → Gardner →
     → sincronismo fino de trama → ecualizador → PLL de fase → decisión
```

**1. Filtro adaptado primero.** Maximiza la SNR en el instante de muestreo y, al
ser el mismo RRC del transmisor, la respuesta conjunta es un coseno alzado, que
cumple Nyquist: sin canal no hay ISI en los instantes de símbolo.

**2. Schmidl-Cox antes que la temporización.** El estimador es **no coherente**
(usa `|P(d)|²`) y opera sobre la señal sobremuestreada, por lo que no necesita
conocer la temporización. Cualquier esquema que necesitase primero recuperar el
reloj sería circular.

> Detalle de implementación que costó un fallo real: la métrica original de
> Schmidl-Cox normaliza sólo con la energía de la **segunda** ventana,
> `M = |P|²/R_b²`. En recepción continua de OFDM da igual, pero en recepción por
> ráfagas no: en el flanco final de la ráfaga la primera ventana todavía contiene
> señal mientras la segunda sólo tiene ruido, `M` puede superar la unidad y
> aparece un máximo espurio a miles de muestras del preámbulo. Normalizando con
> `sqrt(R_a·R_b)` la métrica queda acotada por 1 (Cauchy-Schwarz) y el problema
> desaparece. Ver `comm2.sync.schmidl_cox`.

**3. Gardner después de corregir el CFO grueso, no antes.** El detector de error de
temporización de Gardner no está dirigido por decisión, así que tolera CFO
residual — ésa es precisamente la razón de elegirlo frente a Mueller & Muller,
que trabaja con una muestra por símbolo pero exige conocer la constelación y que
el lazo de portadora haya convergido. El precio de Gardner son dos muestras por
símbolo, que aquí no cuesta nada porque ya trabajamos a 8 muestras/símbolo.

**4. Sincronismo fino contra la secuencia de entrenamiento, no contra el
preámbulo.** El preámbulo `[ZC|ZC]` tiene dos mitades idénticas, de modo que su
autocorrelación **aperiódica** presenta un lóbulo lateral de altura 0,5 en el
desplazamiento ±64. Con multitrayectoria el pico principal cae por debajo de ese
lóbulo y el receptor engancha 64 símbolos tarde. La secuencia PN de entrenamiento
es aperiódica y cuatro veces más larga: su pico es inequívoco.

Además, el máximo de correlación se sitúa donde mejor casa la respuesta dispersiva
del canal, típicamente 1–3 símbolos después del primer rayo. Ésa es justamente la
referencia temporal que debe usar el receptor **sin ecualizar**; si se alineara al
primer rayo, su BER saldría artificialmente mala y la comparación del Experimento 3
sería tramposa. Los ecualizadores entrenados absorben el desplazamiento moviendo
su tap dominante, cosa que se comprueba en la figura de coeficientes de
`exp3_taps_complejidad.png`.

**5. Normalización de ganancia y fase de un tap antes del ecualizador.** Se estima
la ganancia compleja óptima sobre el entrenamiento y se divide. Con eso el
ecualizador inicializado en `w = e_D` produce exactamente la señal sin ecualizar,
de modo que la curva de aprendizaje arranca en el desempeño del caso base y la
comparación es limpia.

**6. Ecualizador antes que el PLL.** Dos razones. La primera es que el detector de
fase dirigido por decisión funciona mucho mejor sobre una constelación ya
compactada. La segunda es más sutil y se descubrió midiendo: el residuo de
frecuencia que deja Schmidl-Cox debe estimarse **después** del ecualizador. Un
estimador ML asistido por datos aplicado antes de ecualizar queda arrastrado por
los términos cruzados de ISI y su error típico sube de 2–5 Hz a 10–25 Hz, es decir,
empeora lo que pretendía corregir. Por eso `ReceiverConfig.fine_cfo` está
desactivado por defecto y la estimación fina se hace sobre `eq.y[:n_train]`.

**7. PLL de fase sembrado, no ensanchado.** El escalón de fase inicial ya lo eliminó
la normalización de un tap, así que al lazo sólo le queda seguir una **rampa**. Un
lazo de segundo orden acaba con error de fase nulo ante un escalón de frecuencia,
pero su transitorio dura ≈ 1/(BnT) símbolos: con BnT = 5·10⁻⁴ son 2 000 símbolos, y
el error de fase acumulado en ese tramo supera el margen de decisión de 16-QAM,
provocando fallos catastróficos intermitentes.

La solución **no** es ensanchar el lazo durante el entrenamiento: la ganancia
integral crece con el ancho de banda y el integrador ejecuta un paseo aleatorio
sobre los símbolos conocidos, terminando con un error de frecuencia mayor del que
se quería corregir (medido: BER de 16-QAM pasa de 2·10⁻³ a 0,45). La solución
correcta es **sembrar el integrador** con la estimación de frecuencia
post-ecualizador, de modo que el lazo arranca ya en régimen permanente.

---

## 5. Ecualización

| Método | Tipo | Coste por símbolo | Conoce el canal | Usa entrenamiento |
|---|---|---|---|---|
| Ninguno | — | 0 | no | no |
| **LMS (método A)** | adaptativo, gradiente estocástico | 8N, `O(N)` | no | sí |
| **RLS (método B)** | adaptativo, mínimos cuadrados recursivo | 16N²+16N, `O(N²)` | no | sí |
| ZF | fijo, inversión de canal | 4N | **sí** | no |
| MMSE | fijo, Wiener | 4N | **sí** | no |
| CMA | adaptativo ciego (Godard) | 8N+4 | no | **no** |

ZF y MMSE se incluyen como **cotas de referencia**, no como candidatos: requieren
un conocimiento perfecto del canal que un receptor real no tiene. Sirven para
saber cuánto margen queda entre lo que consiguen LMS/RLS y lo mejor alcanzable con
un filtro lineal de N taps.

El CMA responde a otra pregunta: cuánto se pierde por prescindir de la secuencia
de entrenamiento. La respuesta medida es que converge un orden de magnitud más
lento y su BER se estanca antes, pero ahorra el 2,5 % de trama del entrenamiento.

**Detalle numérico del RLS.** La recursión de Riccati pierde la simetría hermítica
por redondeo y, con λ < 1, el error se amplifica en 1/λ por iteración hasta que P
deja de ser definida positiva y el algoritmo diverge. Sin la simetrización
`P = (P + Pᴴ)/2` en cada paso, el RLS divergía para λ ≤ 0,995 (BER 0,44 medida).
Con ella funciona en todo el rango λ ∈ [0,95, 1].

---

## 6. Ablaciones disponibles

`ReceiverConfig` permite desactivar cada bloque de forma independiente
(`matched_filter`, `timing_recovery`, `cfo_correction`, `fine_cfo`, `phase_pll`),
lo que hace posible cuantificar la aportación de cada etapa. Los experimentos 2, 3
y 4 usan esa capacidad.
