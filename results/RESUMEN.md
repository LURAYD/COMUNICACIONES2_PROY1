# Resumen de resultados

Configuracion base: `fs=1.000 MHz | sps=8 | Rs=125.0 kBd | mod=QPSK (k=2) | Rb=250.0 kb/s | beta=0.35 | B=168.8 kHz | eta=1.481 b/s/Hz`


## Experimento 1 — validacion en AWGN

| Modulacion | Razon BER sim/teo (mediana) | Razon maxima | Puntos comparados |
|---|---|---|---|
| 16QAM | 1.15 | 1.52 | 7 |
| QPSK | 1.10 | 1.61 | 6 |


## Experimento 2 — efecto de la ISI

| Perfil | tau_rms [T] | Apertura del ojo | EVM [%] | BER |
|---|---|---|---|---|
| flat | 0.000 | 0.764 | 14.3 | < 1e-6 |
| mild | 0.264 | 0.672 | 20.1 | < 1e-6 |
| moderate | 0.622 | 0.115 | 63.6 | 6.11e-02 |
| severe | 1.145 | 0.083 | 502.4 | 4.64e-01 |


## Experimento 3 — comparacion de ecualizadores

| Metodo | BER | MSE residual [dB] | Convergencia a -9 dB [simb] | Mult. reales/simbolo | Orden |
|---|---|---|---|---|---|
| Sin ecualizar | 6.11e-02 | -3.90 | -1 | 0 | - |
| LMS (metodo A) | 2.50e-05 | -12.18 | 78 | 168 | O(N) |
| RLS (metodo B) | < 1e-6 | -11.51 | 60 | 7392 | O(N^2) |
| Zero-Forcing (canal conocido) | 2.50e-05 | -12.28 | 4 | 84 | O(N) |
| MMSE (canal conocido) | < 1e-6 | -12.34 | 5 | 84 | O(N) |
| CMA (ciego) | 7.50e-05 | -10.26 | 1310 | 172 | O(N) |


## Experimento 3 — sensibilidad a mu y lambda

| Metodo | Parametro | Valor | BER | MSE residual [dB] | Convergencia a -6 dB |
|---|---|---|---|---|---|
| lms | mu | 0.02 | 2.15e-03 | -5.69 | 135 |
| lms | mu | 0.05 | 3.58e-03 | -5.41 | 119 |
| lms | mu | 0.1 | 2.00e-04 | -9.87 | 67 |
| lms | mu | 0.2 | 7.50e-05 | -11.64 | 61 |
| lms | mu | 0.5 | 2.50e-05 | -12.18 | 34 |
| lms | mu | 1.0 | 1.00e-04 | -11.90 | 57 |
| rls | lambda | 0.95 | 4.50e-04 | -10.51 | 41 |
| rls | lambda | 0.98 | 7.50e-05 | -11.90 | 41 |
| rls | lambda | 0.99 | 5.00e-05 | -12.30 | 41 |
| rls | lambda | 0.995 | 2.50e-05 | -12.46 | 41 |
| rls | lambda | 0.999 | < 1e-6 | -11.51 | 41 |
| rls | lambda | 1.0 | < 1e-6 | -6.00 | 41 |


## Experimento 4.3 — rango de adquisicion de frecuencia

| Magnitud | Valor |
|---|---|
| Limite medido de adquisicion de CFO | 0.80 % de Rs |
| Limite teorico Rs/(2L) | 0.78 % de Rs |


## Experimento 4.5 — BER frente a longitud del entrenamiento

| Simbolos de entrenamiento | lms | rls |
|---|---|---|
| 64 | 6.25e-05 | < 1e-6 |
| 128 | 6.25e-05 | 3.75e-05 |
| 256 | 3.75e-05 | < 1e-6 |
| 512 | 1.25e-05 | < 1e-6 |
| 1024 | 3.75e-05 | < 1e-6 |


## Experimento 4.7 — Rayleigh: factor de olvido del RLS

| fD/Rs | 0.99 | 0.999 | 0.9999 |
|---|---|---|---|
| 0.0 | 3.11e-02 | 2.13e-02 | 2.09e-02 |
| 5e-05 | 4.79e-03 | 1.66e-01 | 2.52e-01 |
| 0.0002 | 1.48e-01 | 4.22e-01 | 4.01e-01 |
| 0.001 | 4.89e-01 | 4.94e-01 | 4.85e-01 |
| 0.005 | 4.98e-01 | 5.02e-01 | 5.01e-01 |


## Experimento 5 — potencia frente a eficiencia espectral (BER = 1e-3)

| Escenario | Modulacion | k | eta [b/s/Hz] | Eb/N0 medido [dB] | Eb/N0 teorico [dB] | Penalizacion [dB] |
|---|---|---|---|---|---|---|
| A | qpsk | 2 | 1.48 | 6.7 | 6.8 | -0.1 |
| A | 8psk | 3 | 2.22 | 10.2 | 10.0 | 0.1 |
| A | 16qam | 4 | 2.96 | 10.7 | 10.5 | 0.1 |
| A | 64qam | 6 | 4.44 | 15.0 | 14.8 | 0.2 |
| C | qpsk | 2 | 1.48 | 11.2 | 6.8 | 4.4 |
| C | 8psk | 3 | 2.22 | 14.6 | 10.0 | 4.6 |
| C | 16qam | 4 | 2.96 | 18.1 | 10.5 | 7.6 |
| C | 64qam | 6 | 4.44 | — | 14.8 | — |
