# Validación cruzada con GNU Radio Companion

Sección 11 de la guía: *«cada equipo deberá seleccionar un experimento
representativo y reproducirlo utilizando la segunda herramienta (GNU Radio). Se
deberá analizar si ambos resultados son consistentes.»*

El experimento elegido es el **Experimento 2** (efecto de la ISI sobre QPSK con
conformación RRC), porque involucra transmisor, canal y receptor a la vez y sus
métricas —PSD, constelación, EVM, BER— son comparables entre herramientas sin
ambigüedad.

> **Estado de validación.** Los dos `.grc` se escribieron para **GNU Radio
> 3.10**. Están verificados en tres niveles: estructura YAML, coherencia de las
> conexiones, y —bloque por bloque— que el `id` y todos los nombres de parámetro
> coinciden con las definiciones oficiales de `maint-3.10`
> (`gr-digital/grc/*.block.yml` y equivalentes). Lo que **no** se ha podido
> probar es la ejecución, porque la máquina donde se desarrollaron no tiene
> GNU Radio instalado: al abrirlos por primera vez, comprueba que ningún bloque
> salga en rojo antes de ejecutar.
>
> Esa verificación destapó un cambio de API que habría roto el flowgraph:
> **GNU Radio 3.9 eliminó `digital.lms_dd_equalizer_cc` y
> `digital.cma_equalizer_cc`** y los sustituyó por la pareja
> `variable_adaptive_algorithm` (objeto que define el algoritmo: `lms`, `nlms`
> o `cma`) + `digital_linear_equalizer` (el filtro). El flowgraph ya usa la API
> nueva. Si sigues un tutorial escrito para 3.7/3.8, encontrarás los bloques
> antiguos y no existirán en tu instalación.

---

## Formato de intercambio

`complex64` intercalado (I, Q float32), que es el formato interno de GNU Radio.
Desde Python:

```python
x = np.fromfile("grc/io/grc_rx_signal.cf32", dtype=np.complex64)
x.astype(np.complex64).tofile("grc/io/py_tx_signal.cf32")
```

Todos los ficheros de intercambio viven en `grc/io/` (creada automáticamente).

---

## Las dos comparaciones

### A — GNU Radio como transmisor y canal → `tx_qpsk_canal.grc`

```
Random Source → Constellation Modulator (QPSK + RRC) → Channel Model → File Sink
                          │                                    │
                          └── File Sink (TX limpio)            └── File Sink (RX)
```

Valida el **transmisor y el canal**: Python mide sobre el fichero de GRC la PSD,
el ancho de banda ocupado al 99 % y el PAPR, y los contrasta con su propia cadena.
Si la ocupación espectral coincide con `B = Rs(1+β) = 168,75 kHz` en ambas
herramientas, la conformación RRC está implementada igual.

### B — GNU Radio como receptor → `rx_qpsk_desde_python.grc`

```
File Source (señal de Python) → Channel Model → PFB Clock Sync → Costas Loop
                                              → Linear Equalizer → File Sink
                                              + Constellation / PSD / Eye sinks
```

Valida el **receptor**: GRC procesa exactamente la misma forma de onda que genera
el simulador de Python. Como transmisor y canal son idénticos, cualquier
diferencia en BER o EVM es atribuible al receptor. Es la comparación más
informativa de las dos.

Correspondencia entre bloques:

| Bloque de GNU Radio | Equivalente en `comm2` |
|---|---|
| `Polyphase Clock Sync` | `sync.gardner_timing_recovery` (lazo de Gardner) |
| `Costas Loop` (orden 4) | `sync.dd_phase_pll` |
| `Linear Equalizer` + `Adaptive Algorithm (lms)` | `equalizers.run_lms` en modo dirigido por decisión |
| `Channel Model` | `channel.apply_channel` |
| `Constellation Modulator` | `modulation.Modulation` + `pulse.pulse_shape` |

Diferencia conceptual que conviene comentar en el informe: el ecualizador del
flowgraph se deja con `training_sequence` vacía, es decir **puramente dirigido
por decisión**, mientras que el método A de este proyecto entrena primero sobre
512 símbolos conocidos. Es esperable que GRC converja más despacio y sea más
sensible a SNR baja; cuantificar esa diferencia es parte del análisis de
consistencia.

Si quieres una comparación *exacta* con el método A, `digital_linear_equalizer`
admite una `training_sequence` y un `training_start_tag`: se le puede pasar la
secuencia PN que exporta `exp6_validacion_grc.py` en `py_reference.npz`. Requiere
insertar el tag de inicio con un `Correlation Estimator`, lo que complica el
flowgraph; por eso la versión entregada usa el modo ciego, que es además el que
mejor ilustra el coste de prescindir del entrenamiento.

---

## Procedimiento paso a paso

1. **Exporta la señal de referencia desde Python**

   ```bash
   cd experiments
   python exp6_validacion_grc.py --export
   ```

   Genera `grc/io/py_tx_signal.cf32`, `grc/io/py_reference.npz` y
   `grc/io/ch_taps_para_grc.txt`.

2. **Abre `tx_qpsk_canal.grc`** en GNU Radio Companion.
   Pega el contenido de `ch_taps_para_grc.txt` como valor de la variable
   `ch_taps` (son los 62 coeficientes del perfil `moderate` a 8 muestras/símbolo,
   exactamente los mismos que usa la simulación de Python).
   Ajusta `noise_volt` y ejecuta. Produce `grc_tx_bytes.bin`,
   `grc_tx_signal.cf32` y `grc_rx_signal.cf32`.

3. **Abre `rx_qpsk_desde_python.grc`** y ejecútalo. Verás en vivo la
   constelación, la PSD y el diagrama de ojo, y se escribirá
   `grc_rx_symbols.cf32`.

4. **Vuelve a Python para el análisis comparativo**

   ```bash
   python exp6_validacion_grc.py
   ```

   Escribe `results/data/exp6_validacion_cruzada.csv` y
   `results/figures/exp6_validacion_grc.png` con las constelaciones y PSD de
   ambas herramientas lado a lado.

---

## Sobre la calibración de la SNR

El bloque `Channel Model` de GNU Radio especifica el ruido como **tensión**
(`noise_voltage`), no como Eb/N0, y la normalización de potencia del
`Constellation Modulator` depende de la versión. En lugar de intentar calibrar
esa correspondencia a ciegas, `exp6_validacion_grc.py` **estima la SNR realmente
presente** en el fichero recibido (estimador M2M4, `metrics.estimate_snr_m2m4`) y
compara los resultados al SNR medido. Es más robusto y además ejercita un
estimador ciego de SNR, que es materia del segundo proyecto de la asignatura.

Punto de partida razonable: para QPSK con constelación de potencia unitaria y
`sps = 8`, `noise_voltage ≈ 0,1` sitúa la SNR en la zona de 12–15 dB. Barre el
valor y verifica con el script.

---

## Ejecutar sin interfaz gráfica

```bash
grcc tx_qpsk_canal.grc -o .     # genera tx_qpsk_canal.py
python3 tx_qpsk_canal.py
```

`tx_qpsk_canal.grc` está configurado como `no_gui` precisamente para esto.
`rx_qpsk_desde_python.grc` usa `qt_gui` porque su valor añadido es la
representación gráfica que pide la guía.
