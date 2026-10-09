# Formato de la corrida

Una **corrida** es una carpeta con UN enlace simulado y los parámetros con que
se simuló. Es lo único que comparten la aplicación (o cualquier otro
generador) y la parte de GNU Radio. Mientras este formato no cambie, cada lado
puede evolucionar sin romper al otro.

## Cómo generarla

**Desde código Python** (por ejemplo, un botón de la aplicación): basta con el
`LinkResult` de `run_link`:

```python
from comm2 import run_link
from grc.corrida import escribir_corrida      # o sys.path → grc/

r = run_link(p, chan, rx)
escribir_corrida(r, "grc/corridas/mi_corrida", origen="banco de pruebas")
```

**Desde el JSON que ya exporta la aplicación** (sección Exportar → Guardar
JSON, `app/gnuradio_json.py`): el JSON trae los parámetros pero no las señales.
`grc/generar_corrida.py --json fichero.json` vuelve a simular con esos mismos
valores y escribe la corrida. Verificado: el JSON del escenario B de la
aplicación produce una corrida idéntica, byte a byte, a la de
`generar_corrida.py --escenario B --ebn0 12`.

## Contenido

| Fichero | Tipo | Contenido |
|---|---|---|
| `parametros.txt` | texto | los valores usados (ver abajo) |
| `resultados_python.txt` | texto | `ber`, `ber_errores`, `ber_bits`, `evm_pct`, `enganchado` del receptor de Python |
| `simbolos_tx.cf32` | complex64 | símbolos que entran al RRC: guarda + preámbulo ZC + entrenamiento + datos + guarda |
| `senal_tx.cf32` | complex64 | señal transmitida (tras el RRC, antes del canal) |
| `senal_rx.cf32` | complex64 | señal recibida (tras el canal de Python) |
| `simbolos_rx_python.cf32` | complex64 | carga útil a la salida del receptor de Python |

`.cf32` = complex64, I y Q en `float32` intercalados, sin cabecera. Es el
formato del bloque File Source de GNU Radio; en NumPy,
`np.fromfile(f, dtype=np.complex64)` y `x.astype(np.complex64).tofile(f)`.

## `parametros.txt`

Una línea `clave = valor` por parámetro. Lo que va tras `#` es comentario. Los
vectores van en una línea, separados por comas, y cada complejo **sin espacios**
(`+0.8017-0.0199j`), porque `complex()` no admite espacios.

| Clave | Unidad | Significado |
|---|---|---|
| `modulacion` | — | `bpsk`, `qpsk`, `8psk`, `16qam`, `64qam` |
| `fs` | Hz | frecuencia de muestreo |
| `sps` | — | muestras por símbolo |
| `rolloff`, `span` | —, símbolos | RRC con `span·sps+1` coeficientes y energía 1 |
| `zc_len`, `n_train`, `n_payload`, `guard` | símbolos | estructura de la trama |
| `ebn0_db` | dB | Eb/N0 rotulada |
| `noise_voltage` | — | desviación típica del ruido complejo, `√(1/(k·Eb/N0))`; en GNU Radio va tal cual |
| `cfo_hz` | Hz | desplazamiento de frecuencia |
| `fase_grados` | ° | fase fija |
| `reloj_ppm` | ppm | deriva del reloj de muestreo |
| `retardo_frac` | muestras | retardo fijo (GNU Radio no lo reproduce) |
| `rayleigh` | 0/1 | desvanecimiento (GNU Radio no lo reproduce) |
| `taps_canal` | — | canal a **tasa de muestreo**, el que se aplicó de verdad |
| `eq_taps`, `eq_mu`, `ecualizador` | — | ecualizador de Python |
| `semilla` | — | semilla del ruido |

Informativas: `formato`, `escenario`, `perfil`, `n_taps_canal`,
`bits_por_simbolo`.

Las claves obligatorias están en `corrida.OBLIGATORIAS`. `validar_gnuradio.py`
rechaza la corrida si falta alguna, porque si no GNU Radio usaría un valor por
defecto sin avisar y la comparación no valdría nada.
