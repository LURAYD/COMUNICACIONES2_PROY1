# Revisión del trabajo de dake14 frente al libro de Medina

Libro: C. A. Medina C., *Fundamentos de Ingeniería de Comunicación*, Parte 2
(capítulos 9 a 15). Es un PDF escaneado sin capa de texto y no hay versión en
Markdown: se leyó como imagen. «lib N» es la página impresa; la del fichero es
N − 270 (pdf 1 = lib 271).

**Fecha:** 8 de octubre de 2026. **Revisa:** Claude, a petición de Luis.

---

## 0. Qué se revisa y cómo

### Alcance

El trabajo de dake14 son dos commits:

| Commit | Fecha | Qué toca |
|---|---|---|
| `948e725` | 7 oct | `equalizers.py` (convergencia, divergencia, CMA), `metrics.symbol_mse` (EVM acotada), ojo antes/después del ecualizador (`engine._equalize_wave`, `_align_phase`), campaña, exportación, `tests/test_robustez.py`; **borra GNU Radio** |
| `fcf5ce3` | 8 oct | Interfaz por secciones: **1 Generación** (`GenView`), **2 Canal** (`ChanView`), 3 Análisis, **4 Exportar** con JSON para GNU Radio (`app/gnuradio_json.py`); PAPR, canal equivalente `h_sym`, SIR y distorsión de pico en `engine.simulate`; ojo como imagen de densidad |

El núcleo del simulador (`src/comm2`: pulsos, canal, sincronismo, LMS/RLS,
ZF/MMSE) **no es suyo** y ya se cotejó con el libro en
`docs/comparacion_libro_medina.md` (4 de octubre). Aquí solo se juzga lo que
él escribió y lo que sus vistas enseñan. Cuando un fallo es heredado se dice.

### Método

1. **Libro.** Páginas leídas para esta revisión: lib 271–287 (cap. 9 entero
   hasta el ZF), lib 314–319 y 343–344 (QPSK, OQPSK, tabla comparativa del
   cap. 10), lib 377–378 (Eb/N0 del cap. 12).
2. **Código.** Diff de los dos commits, línea a línea en lo que toca a la
   física.
3. **Medida.** Cada punto central se ejecutó en esta máquina. **VERIFICADO**
   significa ejecutado y observado. Se capturaron las tres secciones de la
   aplicación y se compararon sus valores con GNU Radio 3.10.9.2.

Veredictos: **Bien** (coherente con el libro y el número sale), **Con matiz**
(correcto pero hay que declarar o ajustar algo), **Mal** (contradice la teoría
o la representa de forma engañosa), **Fuera del libro** (se evalúa con teoría
estándar).

---

## 1. Resumen

| # | Qué | Dónde | Libro | Veredicto |
|---|---|---|---|---|
| 1 | `Rs`, `Rb`, `k`, `B = Rs(1+β)`, `η = k/(1+β)` | Generación | (9.26), (9.28), Tabla 10.6, Ej. 10.11 | **Bien** |
| 2 | PAPR sobre la señal RRC | Generación | lib 280, lib 317 | **Bien**, con matiz de método |
| 3 | Ojo «tras el RRC» con semáforo de calidad | Generación | (9.6), (9.13), (9.23)–(9.25) | **Mal**: el RRC solo no es Nyquist |
| 4 | Espectro con banda ±(1+β)/2 | Generación, Canal | (9.28), Fig. 9.9 | **Bien** |
| 5 | Canal equivalente `h_sym` | Canal | (9.6), (9.9) | **Bien** el concepto |
| 6 | Distorsión de pico `D` | Canal | lib 287, Ej. 9.5 | **Bien**: reproduce el 0,0955 del libro |
| 7 | SIR y D de los perfiles con ecos fraccionales | Canal | (9.11) | **Con matiz**: hasta 0,75 dB y 0,13 de D distintos de lo que ve el receptor |
| 8 | Constelación y ojo «tras el canal» | Canal | (9.4), (9.8), lib 281, (12.3) | **Mal**: se muestrea antes del filtro receptor |
| 9 | Lectura de Es/N0 | Canal | (12.2), (12.3) | **Con matiz**: valor nominal, no el recibido |
| 10 | Ojo después del ecualizador | Análisis | (9.29), Fig. 9.15, (9.32) | **Bien**: es el ecualizador transversal del libro |
| 11 | Tiempo de convergencia | `equalizers._analyze` | fuera del libro | **Con matiz**: muy ruidoso entre semillas |
| 12 | CMA normalizado | `equalizers.run_cma` | fuera del libro | **Con matiz**: variante propia, probada solo en canal plano; su curva se rotula «MSE» |
| 13 | EVM acotada al 100 % | `metrics.symbol_mse` | fuera del libro | **Bien** |
| 14 | Campaña: BER lineal en eje log, suelo `1/(k·N)` | `campaign.py` | (12.1) | **Bien** |
| 15 | JSON para GNU Radio | Exportar | (9.2), (9.3), (12.3) | **Bien** los valores; **incompleto** para la validación cruzada |
| 16 | Borrado de GNU Radio | `948e725` | Guía §1, §6, §11, entregable d | **Mal** respecto a la guía (ya restaurado aparte) |
| 17 | Flecha «error dirigido por decisión» PLL → ecualizador | diagrama de bloques | Fig. 10.28 | **Mal** (heredado, figura regenerada por él) |
| 18 | Curva de Shannon del experimento 5 | figura regenerada | (12.123) | **Mal** (heredado, ver `comparacion_libro_medina.md` §3.2) |

**Lo más importante:** los puntos 3 y 8. La sección Canal enseña un ojo y una
constelación que **no son los del libro** (están antes del filtro receptor) y
los presenta como el efecto del canal. Un lector concluiría que a 12 dB en
canal plano el ojo está casi cerrado (apertura 0,23), cuando tras el filtro
adaptado está abierto (0,71).

---

## 2. Sección 1 · Generación de onda (`GenView`)

### 2.1 Tasas, ancho de banda y eficiencia — Bien

**Código** (`sections.py`, `GenView.apply`):

```python
p = SystemParams(mod=res.req.mod, beta=res.req.beta)
self.rs.set(f"{p.rs / 1e3:.0f}")          # Rs = fs/sps
self.rb.set(f"{p.rb / 1e3:.0f}")          # Rb = k·Rs
self.bw.set(f"{p.bw / 1e3:.1f}")          # B  = Rs(1+β)
self.eta.set(f"{p.spectral_efficiency:.2f}")  # η = Rb/B = k/(1+β)
```

**Concepto.** Relación entre tasa de bit y de símbolo, y ancho de banda de un
pulso coseno alzado.

**Libro.** `T = T_b·log2 M` (9.26), es decir `Rb = k·Rs`. En banda base,
`B_T = Rs(1+α)/2` (9.28). En pasabanda el ancho se duplica: el Ej. 10.11
(lib 319) da `2Rs` de primer nulo para pulsos rectangulares, y la Tabla 10.6
(lib 344) da `B_T = Rb/2 = Rs` como mínimo de Nyquist para QPSK.

**Juicio.** El proyecto trabaja en banda base **compleja**. Su espectro ocupa
`±Rs(1+β)/2`, que es el equivalente pasabanda de anchura `Rs(1+β)`. Las
cifras de la aplicación (`B` = 168,8 kHz, `η` = 1,48 b/s/Hz para QPSK con
β = 0,35) son las de la Tabla 10.6 con exceso de banda. **Correcto.** Conviene
rotularlo «ancho de banda pasabanda (RF)» para que nadie lo compare con el
(9.28), que es la mitad.

### 2.2 PAPR — Bien, con matiz de método

**Código** (`engine.simulate`):

```python
tx = np.asarray(r.tx_signal)
pw = np.abs(tx[np.abs(tx) > 0]) ** 2
papr = float(10 * np.log10(pw.max() / pw.mean()))
```

**Libro.** Lib 280: *«la razón pico-a-promedio de la señal transmitida se debe
evaluar para una respuesta de raíz de coseno elevado, y no para una respuesta
de coseno elevado»*. Es justo lo que hace: se mide sobre `tx_signal`, que sale
del RRC. Lib 317 explica por qué importa: al filtrar QPSK, los saltos de
±180° hacen fluctuar la envolvente, y eso motiva OQPSK y π/4-QPSK.

**VERIFICADO.** La forma de medirlo (descartando las muestras nulas) da lo
mismo que medir solo sobre la carga útil, con diferencias de 0,01 a 0,03 dB.
En cambio, depende de la longitud de la trama, porque es el máximo de una
muestra aleatoria:

| β | N = 1000 | N = 4000 | N = 20 000 |
|---|---|---|---|
| 0,20 | 5,11 dB | 5,17 dB | 5,44 dB |
| 0,35 | 3,76 dB | 3,93 dB | 3,92 dB |
| 0,50 | 3,21 dB | 3,26 dB | 3,27 dB |
| 1,00 | 3,53 dB | 3,51 dB | 3,58 dB |

**Matices.**
- Con las 1000 muestras de la vista previa (mientras se arrastra) el valor
  baja hasta 0,3 dB.
- La PAPR **no** baja de forma monótona con β: a β = 1 sube respecto a 0,5.
  Si el informe dice «más roll-off, menos PAPR», debe decir «hasta β ≈ 0,5».
- Mejora: dar la PAPR al 99,9 % de la CCDF. Es estable con la longitud y es lo
  que se usa para dimensionar el amplificador.

### 2.3 Ojo «tras el RRC» — Mal (engañoso)

**Código.** `GenView` dibuja el ojo de `taps["rrc"]` (la señal transmitida) y
lo colorea con `_col(op)`: verde si la apertura pasa de 0,5, ámbar o rojo si
no. La nota dice «apertura 0,767» en verde.

**Libro.** El criterio de Nyquist (9.13) se aplica al **pulso total**
`h(t) = h_t ∗ h_c ∗ h_r` (9.6), no al del transmisor. Con el reparto en raíz
de coseno elevado (9.23)–(9.25), el pulso del transmisor es `√H(f)`, que **no**
cumple (9.13): el ojo solo se abre tras el filtro receptor. El libro admite
medir el ojo en el transmisor (lib 281), pero su ejemplo (Fig. 9.12–9.13) usa
un coseno alzado completo en ese punto, no una raíz.

**VERIFICADO.** Sin canal ni ruido (60 dB), el ojo tras el RRC tiene apertura
0,767 y tras el filtro adaptado 0,985. El 23 % que falta es ISI propia de la
raíz, no un defecto del transmisor.

**Juicio.** El número es correcto, pero el semáforo verde y la ausencia de
explicación invitan a leerlo como una medida de calidad. **Corrección:** quitar
el semáforo en este punto y rotular «el RRC solo no cumple Nyquist; el ojo se
abre tras el filtro adaptado (9.25)».

### 2.4 Espectro — Bien

La banda sombreada `±(1+β)/2` en unidades de `Rs` es la (9.28). Los lóbulos
laterales a −45/−60 dB son los del truncado a `span = 10` que el libro ilustra
en la Fig. 9.9 (lib 279). Cada curva se normaliza a su propio pico, lo que
oculta la atenuación absoluta del canal en la sección 2; es aceptable si se
dice.

---

## 3. Sección 2 · Canal (`ChanView`)

### 3.1 Canal equivalente a tasa de símbolo — Bien el concepto

**Código** (`engine.simulate`):

```python
h_sym = symbol_rate_channel(rrc_filter(p.beta, p.span, p.sps),
                            chan.profile.taps(p.sps), p.sps, phase="cursor")
isi = metrics.isi_metrics(h_sym)
```

`symbol_rate_channel` calcula `h ∗ g ∗ h` (RRC del transmisor, canal, RRC del
receptor) y lo diezma a una muestra por símbolo.

**Libro.** Es exactamente `h(t) = h_t ∗ h_c ∗ h_r` (9.6) muestreado en
`t = iT` (9.8)–(9.9): los coeficientes `h_i` cuya suma ponderada da la ISI de
(9.11). La gráfica de tallos con el cursor normalizado a 1 es la misma
representación que el Ej. 9.5 (lib 287).

### 3.2 Distorsión de pico y SIR — Bien la definición, con matiz en los perfiles fraccionales

**Libro.** Lib 287: la distorsión de pico vale `1 − apertura del ojo`, y
`D = 1` significa ojo cerrado. El Ej. 9.5 la calcula como suma de los módulos
de ISI con el cursor a 1: 0,0955.

**VERIFICADO.** `metrics.isi_metrics` sobre la salida del ZF del Ej. 9.5
(`z = 0, −0,0307, 0, 1, 0, −0,0213, 0,0435`) da **D = 0,0955**, el número del
libro. Sobre el pulso sin ecualizar (`0, 0,15, 0,8, −0,3, 0,1`) da 0,6875. La
SIR (potencia del cursor entre potencia de la ISI) no está en el libro con ese
nombre, pero es la razón de los dos términos de (9.11).

**El matiz.** La fase de diezmado `"cursor"` alinea con el trayecto más
fuerte. Se comparó con el canal **que realmente ve el receptor**, estimado
por mínimos cuadrados con los símbolos conocidos a la entrada del ecualizador
(que es el procedimiento del libro, lib 285):

| Perfil | SIR que muestra | SIR medida | D que muestra | D medida |
|---|---|---|---|---|
| Leve | 17,16 dB | 16,78 dB | 0,281 | 0,285 |
| **Moderado** (el de por defecto) | **5,16 dB** | **4,41 dB** | **1,099** | **1,225** |
| Severo | −0,61 dB | −0,55 dB | 2,075 | 2,064 |
| `0,0.2,1,0,0.8` | 1,68 dB | 1,68 dB | 1,000 | 1,004 |

Con ecos a múltiplos de T es exacto. Con el perfil moderado, que tiene ecos a
0,7 y 1,5 T, la vista se queda 0,75 dB optimista. **Corrección:** mostrar la
medida (el receptor ya tiene los símbolos de entrenamiento) o rotular «modelo,
fase del trayecto principal».

El texto de ayuda «D ≥ 1 cierra el ojo de BPSK» es correcto según lib 287.
Para QPSK con coeficientes complejos el criterio por carril es otro;
`isi_metrics` ya lo calcula (`eye_worst_qpsk`) pero la vista no lo usa.

### 3.3 Constelación y ojo «tras el canal» — Mal

**Código.** El punto `"chan"` es `r.rx_signal`, la señal **antes** del filtro
adaptado. La constelación se toma diezmando esa señal en la «fase óptima»
(`best_sampling_phase`), y el ojo se dibuja sobre ella. A diferencia del punto
del filtro adaptado, aquí no se quita el giro de portadora (`_align_phase`
solo se aplica en `"mf"`).

**Libro.**
- La muestra sobre la que se define la ISI y se decide es `y(iT)`, a la
  **salida del filtro receptor** (9.4), (9.8)–(9.9), Fig. 9.3.
- Sobre el ojo, lib 281: *«es de mayor importancia el punto de salida del
  filtro receptor antes del detector»*.
- (12.3): la SNR relevante es la del ancho de banda `W` del filtro receptor.
  Antes de ese filtro el ruido ocupa toda la banda de muestreo.

**VERIFICADO**, canal plano (escenario A), sin ninguna ISI de canal:

| Eb/N0 | Ojo tras el RRC (TX) | Ojo «tras el canal» | Ojo tras el filtro adaptado |
|---|---|---|---|
| 12 dB | 0,767 | **0,230** | 0,712 |
| 30 dB | 0,767 | 0,753 | 0,961 |
| 60 dB | 0,767 | 0,766 | 0,985 |

A 12 dB la vista del canal da un ojo casi cerrado en un canal **sin ISI**. Hay
dos causas, y ninguna es el canal:
- **Ruido sin filtrar.** Con 8 muestras por símbolo, la SNR por muestra antes
  del filtro es `Es/N0 − 10·log10(8)` = 15 − 9 = 6 dB.
- **ISI propia del RRC** (2.3). A 60 dB, el 0,766 es exactamente el del
  transmisor.

En el escenario C, además, la CFO de 375 Hz hace girar la constelación (sale
una nube sin estructura) y el ojo da 0,090. Mezcla CFO, ruido sin filtrar y
ISI propia del RRC con la ISI del canal.

«Muestreada en el instante óptimo» no tiene sentido antes del filtro
adaptado: el instante óptimo se define a su salida (Fig. 9.11).

**Corrección.** O bien se pasa la señal por el filtro adaptado antes de
mostrarla en «Canal», o bien se deja cruda pero sin apertura ni semáforo y
con el rótulo «antes del filtro receptor: ruido de toda la banda e ISI propia
del RRC». La medida que corresponde a esta sección es la del canal
equivalente (3.1), que ya está.

### 3.4 Lectura de Es/N0 — Con matiz

**Código:** `esn0 = ebn0 + 10·log10(k)`. Es la relación `Es = k·Eb`,
correcta.

**Libro.** (12.2)–(12.3) definen Eb/N0 con la energía **recibida**:
`Eb/N0 = (S/N)(W/Rb)`, con `S` la potencia de la señal en el receptor.

**El matiz** (medido en `AGENTS.md` §5). Los perfiles se normalizan con
`Σ|g|² = 1`. Eso conserva la potencia solo si la señal es blanca, y la
señal RRC no lo es. Con ecos fraccionales la potencia útil recibida cambia:
`Pout/Pin` = 1,157 (leve), 0,790 (moderado), 1,005 (severo). En el perfil
moderado, la Es/N0 real en el receptor es **~1 dB menor** que la rotulada.
La lectura debe llamarse «Es/N0 nominal (transmitida)», o mostrar la medida.

---

## 4. Sección 3 · Análisis: lo que cambió dake14

### 4.1 Ojo después del ecualizador — Bien, y fiel al libro

**Código** (`engine._equalize_wave`):

```python
g = np.zeros((w.size - 1) * sps + 1, dtype=complex)
g[::sps] = np.conj(w)            # un coeficiente cada T
full = np.convolve(x, g)
return full[ref_tap * sps: ref_tap * sps + x.size]
```

**Libro.** Es el **ecualizador transversal** de la Fig. 9.15 (lib 285): una
línea de retardo con derivaciones separadas `τ = T` que actúa sobre la forma de
onda continua, con salida `z(k) = Σ x(k−n)·w_n` (9.32). El sistema total es
`H_t·H_c·H_r·H_e` (9.29). Aplicar los pesos cada `sps` muestras sobre la salida
sobremuestreada del filtro adaptado es exactamente esa estructura. En los
instantes de muestreo reproduce los símbolos ecualizados; entre ellos da la
forma de onda real. **Correcto y bien justificado.**

**Matices.**
- El ecualizador aprendió sobre muestras tomadas por Gardner, que sigue la
  fase de muestreo y la deriva de 20 ppm. El ojo usa una fase fija. Es la
  causa más probable (NO VERIFICADO) de que la apertura después (0,365) sea
  menor que la del ojo a tasa de símbolo (0,467).
- `metrics.eye_opening` agrupa por el signo **recibido** y nunca baja de 0
  (trampa de `AGENTS.md`), así que un ojo cerrado aparece como «poco
  abierto». Para comparar con `1 − D` usar `eye_opening_known`.
- `_align_phase` (estimador de fase de potencia M-ésima) no está en el libro.
  Es estándar (Viterbi y Viterbi) y solo se usa para dibujar: no altera el
  receptor.

### 4.2 Tiempo de convergencia — Con matiz (fuera del libro)

El libro no trata algoritmos adaptativos (solo lo menciona en lib 285). En la
teoría estándar (Haykin, *Adaptive Filter Theory*), la curva de aprendizaje es
el **promedio de conjunto** del `|e|²` sobre muchas realizaciones. La
constante de tiempo del LMS es ∝ 1/μ y el RLS converge en unas 2N iteraciones
(~42 con N = 21).

dake14 la redefinió: es el primer símbolo tras el cual la **mediana móvil**
(65 muestras) de una **sola realización** queda a menos de 3 dB del régimen
permanente. Además, -1 cuando no aplica o diverge. Las guardas (no
adaptativo, divergencia, borde de la ráfaga) son correctas y están probadas.

**VERIFICADO**, escenario B, perfil moderado, 20 dB, tres semillas:

| Ecualizador | Convergencia [símbolos] |
|---|---|
| LMS μ = 0,05 | 1741 / 70 / no converge |
| LMS μ = 0,2 | 471 / 223 / 490 |
| LMS μ = 0,5 | 444 / 237 / 133 |
| LMS μ = 1,0 | 485 / 517 / 521 |
| RLS λ = 0,995 | 71 / 288 / 54 |

La dispersión entre semillas es mayor que la diferencia entre algoritmos. El
número que muestra la aplicación («318 símb») no permite afirmar «el RLS
converge antes que el LMS» ni ver la tendencia 1/μ. **Corrección:** promediar
la curva sobre varias realizaciones (la campaña ya repite tramas) o dar la
convergencia como mediana con su rango.

### 4.3 CMA — Con matiz (fuera del libro)

El libro no trae ecualización ciega. El CMA de Godard (p = 2) es
`w ← w − μ(|y|² − R₂)·y*·u`, con `R₂ = E|s|⁴/E|s|²`. El código lo implementa
con el signo y `R₂` correctos, pero cambia el paso:

```python
step = mu_eff / ((np.vdot(u, u).real + 1e-9) * max(abs(yk) ** 2, R2))
```

Normalizar por `‖u‖²` es el CMA normalizado conocido. Dividir además por
`max(|y|², R₂)` es una **variante propia**: estabiliza (lo demuestra la
prueba con μ entre 0,01 y 1), pero cambia el peso de cada muestra en la
condición de equilibrio respecto al CMA de Godard. Hay que nombrarla así en el
informe. El factor `CMA_MU_SCALE = 0,1` ata el paso del CMA al deslizador del
LMS sin fundamento teórico.

**VERIFICADO**, escenario B, tres semillas, carga útil de 4000 símbolos:

| Caso | Sin ecualizar | LMS | CMA, deslizador 0,5 | CMA, deslizador 0,1 |
|---|---|---|---|---|
| QPSK, moderado, 12 dB | 6,6·10⁻² | 4,6·10⁻⁴ | 1,1·10⁻³ | 9,0·10⁻³ |
| QPSK, moderado, 16 dB | 5,7·10⁻² | < 4·10⁻⁵ | < 4·10⁻⁵ | 3,7·10⁻³ |
| QPSK, `0,0.2,1,0,0.8`, 16 dB | 1,9·10⁻¹ | 1,3·10⁻⁴ | 1,3·10⁻² | 1,4·10⁻¹ |
| 16-QAM, moderado, 20 dB | 2,0·10⁻¹ | < 2·10⁻⁵ | 2,6·10⁻² | 1,6·10⁻¹ |

El CMA sí ecualiza, pero mucho más despacio que el LMS entrenado, que es lo
esperable de un método ciego. Con el paso bajo apenas hace nada en la trama.
Dos observaciones:
- `test_robustez` solo prueba el CMA en **canal plano** (escenario A), donde
  no hay nada que ecualizar. Ninguna prueba comprueba que reduzca ISI.
- Su «curva de aprendizaje» es `(|y|² − R₂)²`, el error de **dispersión**,
  dibujado en un eje rotulado «MSE [dB]». En QAM no tiende a cero (el propio
  código lo reconoce con `check_head=False`). Es otra magnitud y debe
  rotularse como tal.

### 4.4 EVM acotada al 100 % — Bien

`symbol_mse` normaliza el error por la potencia de la referencia escalada con
la ganancia óptima, `E|y − a·s|²/E|a·s|²`, que es la definición estándar de EVM
(no está en el libro). Acotarla a 1 evita EVM de miles por ciento cuando la
constelación gira sin corregir. Está probado (`test_evm_*`) y documentado. El
precio: por encima del 100 % todos los fallos se ven iguales.

### 4.5 Campaña — Bien

- La BER se pasa en lineal a un lienzo logarítmico. Antes se aplicaba
  `log10` dos veces y no se dibujaba nada (trampa 11d).
- El suelo medible `1/(k·N)` usa la `k` de la modulación más densa del
  barrido. Es coherente con (12.1): con N finito, BER = 0 solo es una cota.

---

## 5. Sección 4 · Exportar y GNU Radio

### 5.1 Los valores del JSON — Bien (VERIFICADO con GNU Radio)

| Clave | Fórmula | Libro / bloque | Comprobación |
|---|---|---|---|
| `rrc_taps` | `rrc_filter`, `Σh² = 1` | (9.2), (9.24); Interpolating FIR Filter | la corrida que generan (`grc/generar_corrida.py --json`) es idéntica byte a byte a la del simulador |
| `noise_voltage` | `√(1/(k·Eb/N0))` | (12.2)–(12.3); Channel Model (desviación típica del ruido complejo) | en GNU Radio el receptor da la misma BER que Python: 5/8000 errores (`grc/README.md`) |
| `freq_offset_norm` | `CFO/fs` | Channel Model, ciclos por muestra | GNU Radio frente a Python: **−98,4 dB** de diferencia; con el signo cambiado, +2,9 dB |
| `epsilon` | `1 + ppm·10⁻⁶` | Channel Model, razón de relojes | **−65,0 dB** de diferencia |
| `channel_taps_*` | `profile.taps(sps)` | (9.3); Channel Model | los mismos taps que aplica Python |

Las unidades y el sentido de la CFO y del reloj son correctos.

### 5.2 Lo que le falta — incompleto para la §11 de la guía

- **La fase fija se pierde.** El JSON exporta `phase_offset_rad`, pero el
  Channel Model no tiene ese parámetro y la receta (`GRC_SNIPPET`) no añade
  un Multiply Const. En el escenario C, GNU Radio queda **37° girado**
  respecto a Python (medido: falta 37,4°).
- El **retardo fraccional** (`timing_offset_samples` = 0,37) y el
  **Rayleigh** se exportan pero ningún bloque de la receta los aplica, y no
  hay aviso.
- El Channel Model **retrasa 3 muestras**. No importa para el BER, pero sí
  para comparar muestra a muestra.
- Es un JSON de **parámetros**: no lleva los datos, ni la secuencia de
  entrenamiento, ni bloques de receptor. Con él solo no se puede reproducir un
  experimento ni comparar receptores, que es lo que pide la guía §11. Lo
  resuelve `grc/generar_corrida.py --json`, que vuelve a simular con esos
  parámetros y produce las señales.

### 5.3 El borrado de GNU Radio (`948e725`) — Mal respecto a la guía

La guía exige GNU Radio en tres sitios: §1 (*«se debe implementar una
representación equivalente del sistema mediante GNU Radio Companion»*), §6 y
§11 (validación cruzada). Además, el entregable *d* es el flowgraph. El commit
lo borró todo y dejó esos requisitos sin cubrir. Ya está restaurado aparte, en
`grc/`.

---

## 6. Diagramas y figuras

### 6.1 Diagrama de bloques (`results/figures/diagrama_bloques.png`)

Regenerado por dake14 en `948e725`, con código anterior a él.

**Coherente con el libro y con el código:**
- Transmisor: bits → trama → mapeo Gray → RRC. Es Fig. 9.1 y Fig. 10.27,
  con el mapeo Gray de la Fig. 10.26 y `E{|s|²} = 1`.
- Receptor: filtro adaptado → Schmidl-Cox → Gardner → sincronismo de trama →
  ecualizador → PLL → decisión. Es el orden de `link.py`. El filtro adaptado
  va primero, como el filtro receptor de la Fig. 10.28. El ecualizador va
  después del filtro receptor, como en (9.29).
- El rango de Schmidl-Cox, `±Rs/(2L) = ±977 Hz`, es correcto
  (125 000/128 = 976,6 Hz).

**Incorrecto (heredado):** la flecha discontinua «error dirigido por decisión»
va **del PLL al ecualizador**. En el código no existe esa realimentación: el
ecualizador se ejecuta completo y después el PLL procesa su salida. El modo
dirigido por decisión del ecualizador usa sus **propias** decisiones. La
flecha sugiere un lazo conjunto que no hay. Debe ser un lazo del ecualizador
sobre sí mismo.

### 6.2 Figuras de experimentos regeneradas

Mismo código: siguen los defectos ya documentados. El más visible es la curva
de Shannon del experimento 5 (`comparacion_libro_medina.md` §3.2): se dibuja
`log2(1+SNR)` con el eje de Eb/N0 en lugar de `Eb/N0 = (2^η − 1)/η` (12.123).
Error de 1,7 dB en QPSK y de 6,5 dB en 64-QAM. Regenerar no lo corrigió.

### 6.3 Capturas de la aplicación

Se capturaron las secciones 1, 2 y 3 (escenario C, 12 dB, LMS). Lo que se ve
cuadra con lo medido arriba:
- Constelación transmitida limpia.
- Ojo tras el RRC en verde (2.3).
- Nube sin estructura y ojo en rojo en «Canal» (3.3).
- SIR 5,16 dB y D 1,099 (3.2).
- Ojo antes y después del LMS: 0,118 → 0,365 (4.1).
- EVM 31,1 %, BER 3,75·10⁻⁴ y SER = 2·BER, que es la aproximación de Gray
  (12.119).

---

## 7. Lógica general del sistema

El flujo de las secciones (generación → canal → receptor) sigue el modelo del
libro: Fig. 9.1 en banda base, Fig. 10.27 y 10.28 en pasabanda, y (9.29) para
el ecualizador. Las tres secciones leen **la misma corrida** de `run_link`, así
que no se contradicen entre sí. Es una buena decisión de diseño y respeta la
regla del proyecto de que `app/` no reimplementa física.

El fallo de fondo es de **puntos de observación**: las secciones 1 y 2 enseñan
señales en puntos donde el libro no define ojo ni constelación (antes de
completar el pulso de Nyquist) y les ponen el mismo semáforo que a las del
receptor. Las medidas numéricas de canal (`h_sym`, D, SIR) sí están en el sitio
correcto.

---

## 8. Correcciones, por prioridad

1. **Sección Canal, constelación y ojo** (3.3): filtrarlos con el filtro
   adaptado, o quitarles apertura y semáforo y rotular «antes del filtro
   receptor».
2. **Sección Generación, ojo** (2.3): quitar el semáforo y explicar que el RRC
   solo no es Nyquist (9.23)–(9.25).
3. **Exportar** (5.2): añadir a la receta un Multiply Const con
   `exp(j·phase_offset_rad)` y avisar de que el retardo fraccional y el Rayleigh
   no se reproducen.
4. **SIR y D** (3.2): mostrar el canal medido con el entrenamiento, o rotular
   «modelo».
5. **Es/N0** (3.4): rotular «nominal».
6. **Convergencia** (4.2): promediar entre realizaciones antes de dar un
   número.
7. **CMA** (4.3): rotular su curva como «error de dispersión», añadir una
   prueba en canal con ISI y llamarlo «CMA normalizado (variante)».
8. **Diagrama de bloques** (6.1): corregir la flecha PLL → ecualizador.
9. **Experimento 5** (6.2): corregir la curva de Shannon (heredado).
10. **PAPR** (2.2): darla al 99,9 % de la CCDF, o indicar la longitud de la
    trama.

## 9. Correcciones aplicadas (9 de octubre)

Todas las de la sección 8. VERIFICADO después de corregir: 39 pruebas pasan
(37 de antes y 2 nuevas). El invariante 4.1 sigue intacto: EVM `preeq` →
`posteq` 77,1 % → 31,1 % en el escenario C.

| # | Corrección | Dónde | Resultado medido |
|---|---|---|---|
| 1 | Constelación y ojo de «Canal» a la salida del filtro receptor, sin corregir nada (punto `chan_mf`); aviso cuando el CFO los hace girar | `engine.simulate`, `ChanView` | canal plano a 12 dB: apertura 0,23 → **0,712** (igual que tras el filtro adaptado) |
| 2 | Ojo «tras el RRC» sin semáforo, con la nota «medio pulso de Nyquist: se abre tras el filtro adaptado» | `GenView` | — |
| 3 | Receta de GNU Radio: Multiply Const con `cmath.exp(1j·phase_offset_rad)`; lista `_no_reproducible` en el JSON; aviso del retardo de 3 muestras y de cómo hacer la corrida completa | `gnuradio_json.py` | escenario C: `_no_reproducible = [timing_offset_samples]`; D añade `rayleigh` |
| 4 | Canal equivalente, SIR y D **medidos con el entrenamiento** (`engine.measured_channel`); el modelo queda solo de reserva si el receptor no engancha | `engine.py`, `ChanView` | moderado: SIR 5,16 → **4,48 dB** (B, 12 dB); estable entre 4 y 30 dB |
| 5 | «Eb/N0 nominal» y «Es/N0 nominal», con ayuda que cita (12.3) | `ChanView` | — |
| 6 | Convergencia = **primera entrada** en la banda de 3 dB; guarda de divergencia con medianas | `equalizers._analyze` | RLS, cinco semillas: 71/288/54/4146/−1 → **56/53/54/68/62**; LMS μ = 0,5: mediana 210 |
| 7 | CMA documentado como «CMA normalizado (variante)»; su curva se rotula «error de dispersión»; prueba nueva en canal con ISI | `equalizers.run_cma`, `displays.Convergence`, `test_robustez` | `test_cma_reduce_la_isi` pasa |
| 8 | Diagrama: sin flecha PLL → ecualizador; cada bloque se realimenta con sus decisiones | `exp0_diagrama_bloques.py` | figura regenerada |
| 9 | Shannon con `Eb/N0 = (2^η − 1)/η` (12.123) y asíntota en −1,59 dB | `metrics.shannon_ebn0_db`, `exp5_modulacion.py` | QPSK 0,83 dB, 16-QAM 3,61 dB, 64-QAM 6,70 dB |
| 10 | PAPR al 99,9 % de la CCDF; el pico de la trama queda en la ayuda | `engine.papr_ccdf`, `GenView` | QPSK, β = 0,35: 3,56 dB (pico 3,93 dB) |

Además:
- **«Ancho de banda RF»** con ayuda que cita la Tabla 10.6 y (9.28).
- **`Readout.set(color=None)`:** el color se resuelve dentro de la función.
  Antes el valor por defecto se evaluaba al importar y quedaba atado al tema
  de ese momento (trampa 4.4 de `AGENTS.md`).

**Sin regenerar:** las tablas y figuras del experimento 3, que usan
`convergence_symbols`. Reflejarán la nueva definición cuando se vuelva a
ejecutar la campaña.

## 10. Límites de esta revisión

- Del libro se leyeron lib 271–287, 314–319, 343–344 y 377–378. Los capítulos
  11, 13, 14 y 15 no se leyeron: no tocan el trabajo revisado.
- Las medidas son de 1 a 3 tramas por caso. Sirven para decidir si la teoría
  se cumple, no para dar curvas.
- La interfaz se revisó por capturas en una configuración (escenario C, 12 dB,
  LMS) y por su código. No se revisaron todas las combinaciones del rail.
- No se ha modificado código de dake14.
