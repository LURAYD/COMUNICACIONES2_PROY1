# Prompt para búsqueda bibliográfica

Copiar y pegar entero en una herramienta de búsqueda con acceso a literatura
(deep research de un LLM, Elicit, Consensus, Semantic Scholar, o similar).

Está escrito para ser auto-contenido: la herramienta no conoce el proyecto, así
que el contexto va dentro.

---

```
Actúa como bibliotecario de investigación especializado en comunicaciones
digitales y procesado de señal. Necesito una búsqueda de literatura rigurosa,
no un resumen general del campo.

================================================================
CONTEXTO: EL TRABAJO QUE SE QUIERE SITUAR
================================================================

Simulador completo de un enlace digital en banda base compleja, implementado en
Python (NumPy/SciPy) sin bibliotecas de comunicaciones de terceros:

- Modulación: QPSK y 16-QAM con mapeo Gray, energía media unitaria.
- Conformación: Root Raised Cosine, roll-off 0,35, 8 muestras/símbolo,
  Rs = 125 kBd.
- Trama: preámbulo Zadoff-Chu de dos mitades idénticas (2x64), 512 símbolos de
  entrenamiento PN QPSK, carga útil de 8192-20000 símbolos.
- Canal: multitrayecto FIR (cuatro perfiles, tau_rms de 0 a 1,145 T), AWGN,
  offset de frecuencia, offset de fase, error de temporización, deriva de reloj
  en ppm, y desvanecimiento Rayleigh con espectro de Jakes.
- Sincronización: Schmidl-Cox (ráfaga + CFO grueso), detector de error de
  temporización de Gardner con interpolador de Lagrange cúbico y lazo de
  segundo orden, sincronismo fino de trama por correlación, estimador ML de CFO
  por periodograma, PLL de fase dirigido por decisión.
- Ecualización: LMS normalizado, RLS, Zero-Forcing, MMSE y CMA, con métricas de
  BER, MSE residual, velocidad de convergencia y coste computacional en
  multiplicaciones reales por símbolo.
- Validación cruzada contra GNU Radio 3.10 mediante ficheros complex64.
- Campaña reproducible bit a bit (semilla derivada por realización) y pruebas
  que comprueban propiedades teóricas, no valores grabados.
- Interfaz de escritorio que permite observar la señal en ocho puntos de
  derivación de la cadena receptora, con los símbolos alineados índice a índice
  entre etapas.

================================================================
LO QUE YA SE ENCONTRÓ — NO REPETIR ESTA BÚSQUEDA
================================================================

Una búsqueda preliminar ya estableció lo siguiente. Dalo por sabido y no
gastes esfuerzo en redescubrirlo; lo que necesito es lo que hay MÁS ALLÁ.

1. La relación entre el factor de olvido lambda del RLS y la tasa Doppler está
   publicada y es conocida. Existe el resultado de que lambda óptimo se
   relaciona con el tiempo de coherencia normalizado (por ejemplo lambda = 0,9
   para Fd*Ts = 1e-3, con memoria 1/(1-lambda) igual a 1/100 del tiempo de
   coherencia). La línea de RLS con factor de olvido variable (VFF-RLS) viene
   al menos desde los años noventa (Wireless Personal Communications) y sigue
   activa en telemetría, acústica submarina y CDMA.

2. Existe al menos un trabajo que aplica análisis de sensibilidad basado en
   varianza (estrategia Morris-LHS-Sobol) a parámetros de un receptor UWB, para
   cuantificar efectos independientes e interacciones acopladas. Está aplicado
   a TOLERANCIAS DE COMPONENTES, no a elección de algoritmo.

3. Existe una literatura amplia y activa sobre enseñanza de comunicaciones
   digitales con SDR y GNU Radio, en ASEE, Frontiers in Education e IEEE
   Transactions on Education.

Si encuentras que alguno de estos tres puntos es incorrecto o está matizado,
dímelo: es información valiosa.

================================================================
LAS CUATRO PREGUNTAS A RESPONDER
================================================================

Para cada una quiero un veredicto explícito: YA EXISTE / EXISTE PARCIALMENTE /
NO ENCONTRADO, con las referencias que lo sostienen.

P1. ¿Se ha aplicado diseño de experimentos formal (factorial, fraccionado,
    Taguchi, superficie de respuesta) o análisis de sensibilidad global (Sobol,
    Morris, FAST) a la ELECCIÓN DE ALGORITMO Y PARÁMETROS de un receptor
    digital —tipo de ecualizador, longitud del filtro, paso de adaptación,
    factor de olvido, longitud de entrenamiento, anchos de banda de lazo— en
    lugar de a tolerancias de componentes o a parámetros de hardware?

P2. ¿Se ha publicado la observación de que el factor de olvido del RLS es
    irrelevante en canal estático pero decisivo bajo desvanecimiento, con
    cuantificación del salto en BER? Necesito las citas canónicas para
    atribuirlo correctamente, no para reclamarlo.

P3. ¿Existe alguna metodología publicada de VALIDACIÓN CRUZADA REPRODUCIBLE
    entre un simulador propio y GNU Radio (o entre dos herramientas de
    simulación de capa física), con criterios cuantitativos de consistencia?

P4. En la literatura de enseñanza de comunicaciones digitales, ¿existe algún
    trabajo que presente una herramienta que permita observar la señal en
    múltiples PUNTOS DE DERIVACIÓN de la cadena receptora de forma interactiva,
    en lugar de mostrar figuras finales? ¿Y alguno que combine eso con
    reproducibilidad verificada y validación cruzada entre herramientas?

================================================================
CÓMO CONSTRUIR LAS CONSULTAS
================================================================

El problema principal es de vocabulario: el campo no llama a estas ideas como
las llamo yo. Cruza sistemáticamente un término de cada columna.

  ESTADÍSTICA / MÉTODO          COMUNICACIONES / OBJETO
  --------------------          -----------------------
  design of experiments         adaptive equalizer
  factorial design              digital receiver
  fractional factorial          link-level simulation
  Taguchi orthogonal array      receiver parameter optimization
  response surface methodology  transceiver design space
  global sensitivity analysis   PHY parameter tuning
  Sobol indices                 synchronization loop bandwidth
  variance-based sensitivity    equalizer tap length
  Morris screening              training sequence length
  ANOVA main effects            carrier frequency offset
  interaction effects           timing error detector

Las consultas van en INGLÉS, aunque me respondas en español: la literatura
está en inglés y buscar en español devuelve casi nada.

================================================================
DÓNDE BUSCAR, EN ORDEN DE PRIORIDAD
================================================================

1. IEEE Xplore. Es la casa de este campo. Prioriza:
     - IEEE Transactions on Communications
     - IEEE Transactions on Signal Processing
     - IEEE Transactions on Wireless Communications
     - IEEE Transactions on Education   (para P4)
     - Actas de Frontiers in Education (FIE)   (para P4)

2. ASEE PEER (peer.asee.org). Es donde vive gran parte de la literatura de
   enseñanza con SDR y no está indexada en Xplore.

3. Semantic Scholar. Úsalo sobre todo para ENCADENAMIENTO DE CITAS, no para
   búsqueda por palabras clave.

4. arXiv, categoría eess.SP. Para preprints recientes.

5. ScienceDirect / Springer. Signal Processing, Digital Signal Processing,
   Wireless Personal Communications.

================================================================
MÉTODO EXIGIDO
================================================================

No te limites a buscar por palabras clave. Haz encadenamiento de citas:

  a) Localiza un artículo cercano, aunque sea flojo.
  b) Revisa sus REFERENCIAS (hacia atrás: de dónde viene la idea).
  c) Revisa quién lo CITA (hacia delante: qué vino después).
  d) Repite con los dos o tres mejores que aparezcan.

No ancles en artículos con miles de citas (Schmidl-Cox, Proakis): el grafo es
inmanejable. Ancla en trabajos específicos y recientes.

CRITERIO DE PARADA: has terminado cuando tres o cuatro cadenas de búsqueda
distintas te devuelven LOS MISMOS artículos. Si cada consulta nueva trae cosas
nuevas, sigues buscando mal y debes decírmelo en lugar de concluir.

================================================================
QUÉ QUIERO DE VUELTA
================================================================

1. Una tabla con los artículos relevantes: referencia completa, año, venue, qué
   cubre exactamente, y en qué se diferencia de lo descrito en el contexto.

2. Un veredicto explícito por cada pregunta P1 a P4, con las referencias que lo
   sostienen.

3. La lista literal de las consultas que ejecutaste, para que yo pueda juzgar
   si la búsqueda fue amplia o estrecha.

4. Si hay un hueco real, dime EN QUÉ VENUE encajaría y por qué.

================================================================
RESTRICCIONES DE HONESTIDAD
================================================================

- Distingue siempre "no lo encontré" de "no existe". Ausencia de evidencia en
  una búsqueda no es evidencia de ausencia, y quiero que lo digas con esas
  palabras cuando corresponda.
- No inventes referencias. Si no puedes verificar que un artículo existe con
  autores, año y venue concretos, no lo incluyas.
- Si un artículo solo lo conoces por el resumen, dilo.
- Prefiero cinco referencias verificadas a treinta plausibles.
- Si la conclusión es que la idea ya está hecha y no hay hueco, dímelo
  directamente. Es un resultado útil.
```

---

## Notas de uso

**Si la herramienta tiene límite de longitud**, recorta por este orden:
primero la tabla de vocabulario (la puede inferir), después la sección de
método. **Nunca recortes** «LO QUE YA SE ENCONTRÓ» ni «RESTRICCIONES DE
HONESTIDAD»: son las dos que evitan que te devuelva basura o que te haga
perder el tiempo redescubriendo lo de lambda.

**Si la herramienta no tiene acceso a IEEE Xplore** (la mayoría no lo tienen a
texto completo), avísalo en el prompt añadiendo al final:

> Si no tienes acceso a IEEE Xplore, dímelo explícitamente y limita tus
> conclusiones a lo que sí puedes verificar. No extrapoles.

**Después de la primera pasada**, la segunda consulta útil es pedirle que
ejecute el encadenamiento de citas sobre los dos o tres artículos más cercanos
que haya encontrado. Ahí es donde aparece el vocabulario real del subcampo.
