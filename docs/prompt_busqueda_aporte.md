# Prompt de búsqueda — caza de aporte técnico

Segunda versión del prompt de búsqueda. La primera
(`prompt_busqueda_bibliografica.md`) situaba el trabajo en la literatura. Ésta
tiene un objetivo distinto y más exigente: **determinar si hay una contribución
técnica defendible, y si no la hay, decirlo**.

---

```
Actúa como revisor de un comité de programa de una revista de comunicaciones
digitales. Tu trabajo NO es animarme: es determinar si lo que describo contiene
una contribución publicable, y decirme que no si no la contiene.

Prefiero un "esto ya está hecho, aquí están las referencias" a un "podrías
explorar...". Un veredicto negativo bien fundamentado me ahorra meses.

================================================================
EL SISTEMA IMPLEMENTADO
================================================================

Simulador de enlace digital en banda base compleja, Python/NumPy, sin
bibliotecas de comunicaciones de terceros:

- QPSK y 16-QAM, Gray, energía unitaria. RRC roll-off 0,35, 8 muestras/símbolo.
- Canal: multitrayecto FIR (tau_rms 0 a 1,145 T), AWGN, CFO, offset de fase,
  error de temporización, deriva de reloj, Rayleigh con espectro de Jakes.
- Sincronización: Schmidl-Cox, TED de Gardner con Lagrange cúbico y lazo de
  segundo orden, sincronismo fino por correlación, CFO fino por periodograma
  ML, PLL de fase dirigido por decisión.
- Ecualización: LMS normalizado, RLS, ZF, MMSE, CMA. Métricas de BER, MSE
  residual, velocidad de convergencia y coste en multiplicaciones por símbolo.
- Campaña reproducible con semilla derivada; pruebas de propiedades teóricas.

================================================================
ÁNGULOS YA DESCARTADOS — NO LOS PROPONGAS
================================================================

Una búsqueda preliminar cerró estos. Si encuentras que alguno está mal
cerrado, dímelo, pero no me los devuelvas como oportunidades.

DESCARTADO 1. Normalización de la métrica de Schmidl-Cox para recepción por
ráfagas. La literatura ya documenta el uso de un factor de normalización
distinto para evitar detecciones espurias al caer la energía al final de la
ráfaga. Existe además la línea Minn / Park / Wilson-Shang sobre la meseta de
la métrica.

DESCARTADO 2. Relación entre el factor de olvido lambda del RLS y la tasa
Doppler. Establecida. VFF-RLS es línea activa desde los noventa.

DESCARTADO 3. Necesidad de ajustar por separado los hiperparámetros de cada
algoritmo antes de compararlos. Reconocida como buena práctica en trabajos
recientes.

DESCARTADO 4. Análisis de sensibilidad basado en varianza aplicado a
tolerancias de componentes de un receptor. Existe (estrategia Morris-LHS-Sobol
en receptores UWB).

DESCARTADO 5. Herramientas de enseñanza de comunicaciones digitales con SDR. Literatura amplia en ASEE, FIE e IEEE Trans. on Education. NO me
propongas la vía educativa: ya sé que existe y no es lo que busco aquí.

================================================================
LAS TRES HIPÓTESIS DE APORTE A EVALUAR
================================================================

Para cada una: ¿YA ESTÁ HECHO / PARCIALMENTE / HUECO REAL? Con referencias.

H1 — INTERACCIÓN, NO EFECTO PRINCIPAL.
La literatura de comparación de ecualizadores adaptativos reporta efectos
principales: "RLS converge más rápido que LMS", "el coste del RLS es O(N^2)".
Mi observación es que la ORDENACIÓN entre métodos se invierte según la región
del espacio de parámetros. Dato crudo: con paso mu = 0,15 el LMS normalizado
falla por completo con 64 símbolos de entrenamiento y se degrada al alargar el
filtro; con mu = 0,5 ese fallo desaparece y ambos métodos quedan por debajo de
1e-4 en todo el barrido de N (5 a 41 taps) y de entrenamiento (64 a 1024).
Es decir: la respuesta a "¿compensa el RLS?" es una función de mu.

  ¿Existe algún trabajo que trate esto como una INTERACCIÓN ESTADÍSTICA
  (diseño factorial, ANOVA con términos de interacción, superficie de
  respuesta) en lugar de como una serie de barridos de un factor a la vez?

H2 — RANKING DE FACTORES POR VARIANZA DE BER.
¿Se han calculado índices de Sobol (o equivalente global) sobre una cadena
receptora completa para ordenar qué parámetro —tipo de ecualizador, N taps,
mu, lambda, longitud de entrenamiento, ancho de banda de los lazos, offset de
frecuencia— domina la varianza de la BER, incluyendo términos de interacción
de segundo orden?

  Ojo: no busco sensibilidad a tolerancias de componentes (descartado 4), sino
  a ELECCIONES DE DISEÑO ALGORÍTMICO.

H3 — POSICIÓN EN LA CADENA QUE INVIERTE EL SIGNO DE UNA MEJORA.
Observación medida: un estimador ML de offset de frecuencia asistido por datos
(periodograma sobre la secuencia de entrenamiento) EMPEORA el resultado si se
aplica antes del ecualizador, porque los términos cruzados de la ISI lo
sesgan: su error típico sube de 2-5 Hz a 10-25 Hz respecto al residuo que
dejaba el estimador grueso. Aplicado después del ecualizador, sí mejora.

  ¿Está cuantificado en la literatura el sesgo que la ISI induce sobre
  estimadores de frecuencia asistidos por datos, y la consiguiente restricción
  de orden en la cadena receptora? ¿Es folklore conocido o hay un resultado
  citable?

================================================================
CÓMO BUSCAR
================================================================

Cruza método estadístico con objeto de comunicaciones. Consultas en INGLÉS
aunque respondas en español.

  MÉTODO                        OBJETO
  ------                        ------
  factorial design              adaptive equalizer selection
  interaction effect            LMS RLS comparison
  response surface              step size training length
  Sobol / variance-based        bit error rate variance
  global sensitivity analysis   receiver chain parameters
  screening design              synchronization loop bandwidth
  ANOVA                         equalizer tap length
  design of experiments         data-aided frequency estimation
                                ISI bias carrier estimation
                                estimator ordering receiver chain

Para H3 añade específicamente: "data-aided frequency offset estimation" +
("ISI" OR "intersymbol interference") + (bias OR degradation); y
"joint equalization and synchronization" + ordering.

DÓNDE, por prioridad:
  1. IEEE Xplore: Trans. Communications, Trans. Signal Processing,
     Trans. Wireless Communications, Signal Processing Letters.
  2. Elsevier Signal Processing / Digital Signal Processing.
  3. EURASIP Journal on Advances in Signal Processing.
  4. arXiv eess.SP.
  5. Semantic Scholar SOLO para encadenamiento de citas.

MÉTODO: encadenamiento hacia atrás (referencias) y hacia delante (quién cita),
partiendo de artículos específicos y recientes, no de los muy citados.

PARADA: cuando varias cadenas distintas devuelvan los mismos artículos. Si
cada consulta sigue trayendo cosas nuevas, dímelo en vez de concluir.

================================================================
QUÉ QUIERO DE VUELTA
================================================================

1. Veredicto por hipótesis: YA ESTÁ HECHO / PARCIALMENTE / HUECO REAL, con
   referencias verificables (autores, año, venue).

2. Si alguna es HUECO REAL: qué EXPERIMENTO MÍNIMO haría falta para
   sostenerla. Concreto: cuántos factores, cuántos niveles, cuántas réplicas
   Monte Carlo, qué análisis. No "habría que investigar más".

3. Si todas están hechas: dímelo sin rodeos y señala el trabajo más cercano a
   cada una, para poder citarlo y posicionarme respecto a él.

4. Venue realista si hay algo: revista o congreso concreto, y por qué ése.

5. La lista literal de consultas ejecutadas.

================================================================
RESTRICCIONES
================================================================

- No inventes referencias. Sin autores, año y venue verificables, no la
  incluyas.
- Distingue "no lo encontré" de "no existe", con esas palabras.
- Si solo conoces un artículo por el resumen, dilo.
- No me propongas la vía educativa ni de herramienta docente. Está descartada.
- No suavices un veredicto negativo. Si esto es un ejercicio de asignatura bien
  hecho sin contribución publicable, ésa es la respuesta correcta y la quiero.
```

---

## Cómo leer la respuesta

Si te devuelve **HUECO REAL en H1 o H2**, el trabajo que falta es la Capa 2:
matriz factorial cerrada, réplicas Monte Carlo suficientes para separar la
varianza del factor de la del ruido, ANOVA con términos de interacción y
después Sobol. Sin eso no hay nada que defender, solo una intuición.

Si te devuelve **todo hecho**, es un buen resultado: has ahorrado meses y
tienes las citas para posicionar tu informe correctamente.

**H3 es la más probable de estar en folklore sin cita.** Si nadie lo ha
cuantificado, es el aporte más barato de los tres: ya tienes la medida
(2-5 Hz frente a 10-25 Hz) y solo hace falta caracterizarla en función de la
severidad del multitrayecto.
