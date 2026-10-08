# Especificación y justificación de parámetros

La guía exige explícitamente que «los parámetros utilizados deberán ser
especificados y justificados» (sección 7). Este documento recoge cada valor y el
motivo de haberlo elegido. Todos los números son reproducibles ejecutando
`experiments/`; las tablas de resultados están en `results/data/`.

---

## 1. Parámetros del enlace

| Parámetro | Valor | Justificación |
|---|---|---|
| `fs` | 1,0 MHz | Frecuencia de muestreo del simulador. No hay portadora de RF: se trabaja en envolvente compleja, así que `fs` sólo tiene que cubrir el ancho de banda de banda base con margen. |
| `sps` | 8 muestras/símbolo | Debe ser ≥ 2 para el TED de Gardner y ≥ 2(1+β) para no aliasar el RRC. 8 deja margen holgado para colocar ecos en retardos fraccionarios y para dibujar diagramas de ojo legibles, con un coste de cómputo todavía moderado. |
| `Rs` | 125 kBd | Consecuencia de `fs/sps`. |
| `T` | 8 µs | Periodo de símbolo. |
| `β` | 0,35 | Compromiso clásico: exceso de banda del 35 % a cambio de una respuesta al impulso que decae rápido, con lo que un filtro de 10 símbolos ya deja ISI residual despreciable. Es además el valor usado en DVB-S y en IS-95, lo que facilita comparar con la literatura. |
| `span` | 10 símbolos (81 taps) | Verificación numérica del criterio de Nyquist sobre la respuesta conjunta RRC⊗RRC: pico = 1,000 y ISI residual total = 0,0075 (−42 dB). Ver `comm2.pulse.excess_bandwidth_check`. |
| `B` | 168,75 kHz | `B = Rs(1+β)`. |
| `η` | 1,48 b/s/Hz (QPSK) · 2,96 (16-QAM) | `η = k/(1+β)`. |

## 2. Estructura de trama

| Campo | Valor | Justificación |
|---|---|---|
| Preámbulo | 2 × 64 símbolos Zadoff-Chu (raíz 25) | La longitud de cada mitad, `L`, fija el rango de adquisición de frecuencia: `\|f\| < Rs/(2L) = 977 Hz = 0,78 % de Rs`. Con 64 símbolos ese rango cubre con holgura el CFO especificado (0,3 % de Rs) y aún deja margen ×2,6. Raíz 25, coprima con 64, como exige la construcción Zadoff-Chu. |
| Entrenamiento | 512 símbolos PN QPSK | Cubre el peor caso de convergencia del LMS medido (≈ 500 símbolos con μ = 0,02) con margen. Ver `results/data/exp4_5_taps_entrenamiento.csv`. |
| Guarda | 64 símbolos | Debe superar el retardo de grupo del RRC (5 símbolos por filtro, 10 en la cascada TX+RX) más la dispersión del canal (hasta 3,6 T). 64 es conservador y su coste es despreciable. |
| Sobrecarga total | 7,2 % con carga útil de 8 192 símbolos; 3,1 % con 20 000 | Precio de la sincronización y el entrenamiento. |

## 3. Perfiles multitrayectoria

Todos los perfiles están normalizados a energía unitaria: el canal introduce ISI
y selectividad **sin** cambiar la SNR media.

| Perfil | Retardos [T] | Ganancias [dB] | τ_rms | τ_rms [µs] | Bc ≈ 1/(5τ_rms) | B/Bc |
|---|---|---|---|---|---|---|
| `flat` | (0) | (0) | 0 | 0 | ∞ | 0 |
| `mild` | (0; 0,5; 1,2) | (0; −8; −14) | 0,264 T | 2,11 | 94,7 kHz | 1,78 |
| `moderate` | (0; 0,7; 1,5; 2,4) | (0; −4; −8,5; −12) | 0,622 T | 4,97 | 40,2 kHz | 4,20 |
| `severe` | (0; 1,0; 2,3; 3,6) | (0; −1,5; −4; −7) | 1,145 T | 9,16 | 21,8 kHz | 7,73 |

**Justificación física.** Con `Rs = 125 kBd`, los valores de τ_rms de 2 a 9 µs
corresponden a propagación exterior en entorno urbano y suburbano con reflexiones
lejanas, que es el régimen típicamente reportado en la literatura para enlaces
móviles terrestres de banda estrecha. El criterio de diseño es que **B > Bc** en
todos los casos con eco, es decir, canal selectivo en frecuencia: si el canal
fuese plano no habría ISI que ecualizar y el proyecto perdería su objeto. La
relación B/Bc de 1,8 a 7,7 cubre desde selectividad leve hasta severa.

Los retardos son deliberadamente **fraccionarios** (0,5 T, 0,7 T, 2,3 T…). Un
canal con retardos enteros en símbolos es un caso particular benigno: la
ecualización a tasa de símbolo lo resuelve con exactitud. Los retardos
fraccionarios obligan al ecualizador a trabajar contra un canal equivalente que
depende de la fase de muestreo, que es la situación realista. Se implementan con
interpoladores sinc enventanados de 41 taps (`comm2.pulse.frac_delay_taps`).

El perfil `severe` tiene el segundo rayo a sólo −1,5 dB del principal: es un eco
casi coherente que produce nulos espectrales profundos. Es el caso donde un
ecualizador lineal de N taps empieza a fallar por amplificación de ruido, y por
eso se incluye en el barrido de robustez.

## 4. Perturbaciones adicionales (escenario C)

| Perturbación | Valor | Justificación |
|---|---|---|
| Offset de frecuencia | 0,3 % de Rs = 375 Hz | Dentro del rango de adquisición de Schmidl-Cox (977 Hz) con margen ×2,6. En términos absolutos, 375 Hz corresponde a una tolerancia de cristal de ±0,17 ppm a 2,1 GHz, o a un Doppler de 195 km/h a esa portadora: es un valor exigente pero físicamente realizable. |
| Offset de fase | 37° | Valor arbitrario no múltiplo de 90°, elegido precisamente para que no coincida con la simetría de la constelación y no pueda «acertarse» por casualidad. |
| Error de temporización | 0,37 muestras (0,046 T) | Retardo fraccionario fijo, no múltiplo de la rejilla de muestreo, que obliga al interpolador del lazo de Gardner a trabajar. |
| Deriva de reloj | 20 ppm | Tolerancia típica de un cristal TCXO de consumo. Sobre una trama de 20 000 símbolos supone una deriva acumulada de 3,2 muestras: suficiente para que un diezmado fijo falle y el lazo de temporización sea imprescindible. |

## 5. Escenario D — desvanecimiento Rayleigh

| Parámetro | Valor | Justificación |
|---|---|---|
| Espectro Doppler | Jakes | Modelo estándar para dispersión isótropa en el plano horizontal. |
| fD/Rs | 2·10⁻⁴ (nominal) | fD = 25 Hz, que a 2,1 GHz corresponde a ≈ 13 km/h. El tiempo de coherencia ≈ 0,4/fD = 16 ms es mucho mayor que la duración de la ráfaga (1,6 ms con 20 000 símbolos), así que el canal es lento respecto a la trama y el ecualizador adaptativo puede seguirlo en modo dirigido por decisión. |
| Barrido | fD/Rs ∈ {0; 5·10⁻⁵; 2·10⁻⁴; 10⁻³; 5·10⁻³} | Cubre desde canal cuasi-estático hasta desvanecimiento rápido, donde el factor de olvido del RLS deja de ser irrelevante. |

## 6. Parámetros del receptor

| Parámetro | Valor | Cómo se eligió |
|---|---|---|
| `timing_loop_bw` (BnT de Gardner) | 0,02 | **Medido**, no supuesto (`exp4_6_lazos.csv`). El compromiso sólo se aprecia con una constelación densa cerca de su umbral, así que se barre con 16-QAM en AWGN a 10 dB (BER teórica 1,75·10⁻³): BnT = 0,002 → 2,19·10⁻² porque la adquisición no termina antes de la secuencia de entrenamiento y queda un error de temporización estático; BnT = 0,02 → **2,04·10⁻³**, prácticamente la teoría; BnT = 0,05 → 2,88·10⁻³ por jitter; BnT = 0,1 → 0,447, el lazo pierde el enganche. |
| `phase_loop_bw` (BnT del PLL) | 5·10⁻⁴ | **Medido** (`exp4_6_lazos.csv`), con QPSK en el escenario C a 6 dB, donde coexisten residuo de frecuencia y SNR moderada: BnT = 5·10⁻⁵ → 0,190 porque el lazo no sigue la rampa de fase que deja el estimador grueso; BnT = 5·10⁻⁴ → **4,15·10⁻²**, el mínimo; BnT = 5·10⁻³ → 0,430 por deslizamientos de ciclo. En AWGN puro (escenario A, 2 dB) la curva es plana entre 10⁻⁴ y 2·10⁻³ y sólo se rompe en 5·10⁻³, lo que confirma que es el residuo de frecuencia —no el ruido— quien fija el extremo inferior. |
| Semilla del PLL | CFO residual estimado tras el ecualizador | Elimina el transitorio de 2 000 símbolos del lazo de segundo orden. Sin esta siembra, 16-QAM presentaba fallos catastróficos intermitentes (1 trama de cada 6). |
| `fine_cfo` | desactivado | La estimación fina **antes** del ecualizador está sesgada por ISI: error típico 10–25 Hz frente a los 2–5 Hz que ya deja Schmidl-Cox. Se conserva el código para la ablación del informe. |
| `n_taps` del ecualizador | 21 | Debe cubrir la dispersión del canal equivalente (hasta ≈ 4 T con el perfil severo, más las colas del RRC). El barrido del Experimento 4.5 muestra el codo de la curva BER vs N. |
| `ref_tap` | N/2 = 10 (centro) | Permite al ecualizador compensar retardos tanto positivos como negativos respecto a la referencia de sincronismo. |
| `mu` del LMS | 0,50 (normalizado) | **Medido**. Barrido del Experimento 3: μ = 0,02 tarda 511 símbolos en llegar a −9 dB y no converge dentro del entrenamiento; μ = 0,5 llega en 78 y alcanza el mejor MSE residual (−12,2 dB); μ = 1,0 empeora por desajuste. El efecto sobre la BER es grande: a 14 dB en el escenario B, 2,2·10⁻³ con μ = 0,15 frente a 4,2·10⁻⁵ con μ = 0,5. Barrido completo en `exp3_sensibilidad_parametros.csv`. |
| `lam` del RLS | 0,999 | Para canal estático cualquier λ ∈ [0,95; 1) converge igual de rápido (≈ 2N iteraciones); λ importa al **seguir** un canal variable, y ahí el Experimento 4.7 muestra el óptimo. λ = 1 (memoria infinita) es la peor opción cuando el canal cambia. |
| `delta` del RLS | 0,01 (P₀ = 100·I) | Inicialización estándar: P₀ grande equivale a poca confianza inicial, lo que acelera las primeras iteraciones. |

## 7. Definición de Eb/N0

```
σ² = Es / (k · Eb/N0),      Es = 1
```

Se añade ruido blanco gaussiano complejo circularmente simétrico de varianza total
σ² a la señal recibida, antes del filtro adaptado. Con la constelación y el RRC
normalizados a energía unitaria, la SNR por símbolo tras el filtro adaptado es
exactamente `Es/N0 = 1/σ²`, independientemente de `sps`.

La equivalencia con la SNR medida en el ancho de banda ocupado es

```
SNR|B = Eb/N0 + 10 log10(k) − 10 log10(1+β)
```

(implementada en `comm2.channel.snr_db_from_ebn0`).
