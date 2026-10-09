"""Sistema de diseno del banco de pruebas.

Dos modos. El **claro** es el de serie: superficies blancas sobre una ilustracion
de fondo, que asoma a traves del rail y de la cabecera y queda tapada bajo los
paneles de datos. El **oscuro** (`--tema oscuro`) conserva el instrumento de
fosforo, que proyecta peor en un aula iluminada pero se lee mejor en portatil.

En claro la densidad de simbolos se lee como TINTA: al superponerse marcas
semitransparentes sobre blanco el resultado se oscurece. En oscuro se lee como
FOSFORO: al superponerse sobre negro, se aclara. Es el mismo dato y la misma
mecanica de composicion; solo cambia el sentido de la acumulacion.

Paleta categorica: instancia documentada del metodo de visualizacion de datos,
orden fijo, nunca ciclada. Validada con el comprobador del metodo:

  claro / blanco #ffffff  - 6 ranuras adyacentes: CVD dE 9.1, vision normal 19.6
                            3 ranuras todos los pares: CVD dE 9.2, normal 24.0
                            aviso de contraste en aqua, amarillo y magenta ->
                            resuelto por la regla de alivio: toda serie lleva
                            leyenda visible, nunca color a secas.
  oscuro / #0c1116        - 6 ranuras adyacentes: CVD dE 8.4, vision normal 19.3
                            3 ranuras todos los pares: CVD dE 9.4, normal 20.9
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor, QFont, QFontDatabase

FONT_DIR = Path(__file__).parent / "fonts"
ASSET_DIR = Path(__file__).parent / "assets"

# Fondo de la aplicacion. Si el fichero no esta, se usa el color liso y no pasa
# nada mas: la aplicacion nunca depende de un recurso que puede faltar.
BACKGROUND_CANDIDATES = ("fondo.png", "fondo.jpg", "fondo.jpeg", "fondo.webp")


def background_path() -> Optional[Path]:
    for name in BACKGROUND_CANDIDATES:
        p = ASSET_DIR / name
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Los dos modos
# ---------------------------------------------------------------------------

# Tintas planas medidas sobre la propia ilustracion (recuento de pixeles, no
# estimadas a ojo). Mandan en el chasis: fondo, cabecera, rail y acentos.
ART_PINK    = "#f09ccc"   # 27 % de la imagen — L 0.79  H 345
ART_NAVY    = "#0c246c"   # 12 %              — L 0.30  H 265
ART_PERI    = "#7878e4"   #  7 %              — L 0.62  H 281
ART_STEEL   = "#3078b4"   #  6 %              — L 0.56  H 247
ART_YELLOW  = "#e4e478"   #  6 %              — L 0.90  H 109

LIGHT = dict(
    # --- superficies ---
    GROUND="#f3eef7",          # solo visible si falta la imagen de fondo
    PANEL="#ffffff",           # superficie de datos (la validada)
    # Reparto de la ilustracion por jerarquia de lectura: manda en la
    # cabecera, que es la banda de identidad; asoma apenas bajo el rail y la
    # lectura de medidas, que son texto denso; y desaparece bajo los paneles de
    # datos, que son blanco opaco.
    RAISED="rgba(255,255,255,242)",    # 95 % - rail y barra de medidas
    HEADER="rgba(255,255,255,199)",    # 78 % - aguada, pero el texto se lee
    PROFILE_FILL=0.22,
    RAISED_SOLID="#f8f5fb",
    RAISED_HI="#ece7f6",
    RULE="#e4dff0",
    RULE_STRONG="#c8c0e0",
    SCRIM=0.62,                # velo blanco sobre la imagen de fondo

    # --- tinta: el azul marino de la ilustracion, no un gris cualquiera ---
    INK=ART_NAVY,              # 13.9:1 sobre blanco
    INK_DIM="#414d87",         #  7.4:1
    INK_FAINT="#6f79a8",       #  4.6:1  minimo de texto de cuerpo
    INK_GHOST="#c3c7e0",       #  1.8:1  solo rejilla, nunca texto

    # --- paleta categorica: instancia documentada, columna clara ---
    # La ilustracion NO puede dar esto. Medido: sus tonos se agrupan en
    # 247/265/281/286 (todos azul-violeta) mas rosa 345 y amarillo 109, y como
    # conjunto categorico falla - rosa y amarillo quedan fuera de la banda de
    # luminosidad, y periwinkle contra azul acero da dE 11.2 en vision normal,
    # bajo el suelo de 15. Sirve para el chasis; no para distinguir cinco series.
    S1="#2a78d6", S2="#eb6834", S3="#1baf7a",
    S4="#eda100", S5="#e87ba4", S6="#008300",

    # La traza de senal no es una serie: es el sujeto, y ahi si manda la
    # ilustracion. Es su periwinkle llevado a la banda valida: pasa luminosidad,
    # croma y contraste >= 3:1 sobre blanco.
    SIGNAL="#5a4fd6",
    SIGNAL_HI="#4a3aa7",       # paso oscuro del mismo tono, para el nucleo
    SIGNAL_ALT="#e87ba4",
    REFERENCE="#414d87",
    HALO_ALPHA=0.10,           # la tinta se acumula hacia oscuro
    CORE_ALPHA=0.78,
    EYE_BLOOM=0.045,
    EYE_TRACE=0.13,

    GOOD="#0ca30c", WARNING="#fab219", SERIOUS="#ec835a", CRITICAL="#d03b3b",

    # --- acentos del chasis, directos de la ilustracion ---
    ACCENT=ART_PERI, ACCENT_WARM=ART_PINK, ACCENT_HI=ART_YELLOW,
)

DARK = dict(
    GROUND="#07090c",
    PANEL="#0c1116",
    RAISED="rgba(18,25,32,240)",
    HEADER="rgba(18,25,32,190)",
    PROFILE_FILL=0.13,
    RAISED_SOLID="#121920",
    RAISED_HI="#18222b",
    RULE="#1c252e",
    RULE_STRONG="#2a3742",
    SCRIM=0.72,                # velo oscuro sobre la imagen de fondo

    INK="#e8eef4",
    INK_DIM="#93a3b2",
    INK_FAINT="#93a3b2",
    INK_GHOST="#33414d",

    S1="#3987e5", S2="#d95926", S3="#199e70",
    S4="#c98500", S5="#d55181", S6="#008300",

    SIGNAL="#199e70",
    SIGNAL_HI="#1fb882",
    SIGNAL_ALT="#d95926",
    REFERENCE="#93a3b2",
    HALO_ALPHA=0.13,           # el fosforo se acumula hacia claro
    CORE_ALPHA=0.85,
    EYE_BLOOM=0.055,
    EYE_TRACE=0.16,

    GOOD="#0ca30c", WARNING="#fab219", SERIOUS="#ec835a", CRITICAL="#d03b3b",

    ACCENT="#199e70", ACCENT_WARM="#d95926", ACCENT_HI="#c98500",
)

MODE = "light"

# Nombres que el resto de la aplicacion lee. `set_mode` los reescribe.
GROUND = PANEL = RAISED = HEADER = RAISED_SOLID = RAISED_HI = RULE = RULE_STRONG = ""
INK = INK_DIM = INK_FAINT = INK_GHOST = ""
S1 = S2 = S3 = S4 = S5 = S6 = ""
SIGNAL = SIGNAL_HI = SIGNAL_ALT = REFERENCE = ""
GOOD = WARNING = SERIOUS = CRITICAL = ""
ACCENT = ACCENT_WARM = ACCENT_HI = ""
SCRIM = HALO_ALPHA = CORE_ALPHA = EYE_BLOOM = EYE_TRACE = PROFILE_FILL = 0.0
SERIES: tuple = ()
# Alias historico: el chasis mas profundo. En claro ya no es un bisel.
BEZEL = ""


def set_mode(mode: str = "light") -> None:
    """Fija el modo. Debe llamarse ANTES de construir ningun widget."""
    global MODE, SERIES, BEZEL
    MODE = "dark" if str(mode).lower() in ("dark", "oscuro") else "light"
    table = DARK if MODE == "dark" else LIGHT
    g = globals()
    g.update(table)
    g["SERIES"] = (table["S1"], table["S2"], table["S3"],
                   table["S4"], table["S5"], table["S6"])
    g["BEZEL"] = table["GROUND"]


set_mode("light")


def rgba(hex_color: str, alpha: float) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


# ---------------------------------------------------------------------------
# Tipografia
# ---------------------------------------------------------------------------

SANS = "IBM Plex Sans"
MONO = "IBM Plex Mono"

_loaded = False


def load_fonts() -> None:
    """Registra las IBM Plex empaquetadas. Sin esto no hay voz tipografica."""
    global _loaded
    if _loaded:
        return
    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    _loaded = True


def font(size: float = 10.5, weight: int = 400, mono: bool = False,
         tracking: float = 0.0, caps: bool = False) -> QFont:
    f = QFont(MONO if mono else SANS)
    f.setPointSizeF(size)
    f.setWeight(QFont.Weight(weight))
    if tracking:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    if caps:
        f.setCapitalization(QFont.Capitalization.AllUppercase)
    if mono:
        # Cifras de ancho fijo: una medida que cambia no debe mover la maqueta.
        f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def f_title():    return font(15.5, 600, tracking=-0.15)
def f_panel():    return font(8.5, 600, tracking=1.15, caps=True)
def f_body():     return font(10.5, 400)
def f_label():    return font(10, 500)
def f_small():    return font(9, 400)
def f_value():    return font(15, 500, mono=True, tracking=-0.4)
def f_value_lg(): return font(19, 500, mono=True, tracking=-0.6)
def f_unit():     return font(9, 400, mono=True)
def f_axis():     return font(8.5, 400, mono=True)
def f_stage():    return font(9.5, 500)
def f_stage_n():  return font(8.5, 500, mono=True)


# ---------------------------------------------------------------------------
# Hoja de estilo
# ---------------------------------------------------------------------------

def stylesheet() -> str:
    # El chasis no declara fondo: lo pinta la ventana con la ilustracion. Las
    # superficies con nombre son las unicas que lo declaran, y las de chrome lo
    # hacen con alfa para que la imagen asome.
    return f"""
/* Sin fondo global a proposito. Una hoja de estilo puesta sobre un contenedor
   se hereda a TODOS sus hijos y les pisa el fondo - asi es como un boton
   primario acaba pintado del color del chasis. */
QWidget {{
    color: {INK};
    font-family: "{SANS}";
}}

/* #Backdrop pinta la ilustracion por su cuenta (ver backdrop.py); el resto del
   chasis queda transparente para no taparla. */
QMainWindow {{ background: {GROUND}; }}
#Shell, #Body, #Stack, QStackedWidget {{ background: transparent; }}

QToolTip {{
    background: {RAISED_SOLID};
    color: {INK};
    border: 1px solid {RULE_STRONG};
    padding: 5px 8px;
    font-size: 10pt;
}}

/* ---- Superficies nombradas ------------------------------------------- */
QScrollArea#Rail {{ background-color: {RAISED}; border: none; border-right: 1px solid {RULE_STRONG}; }}
QWidget#RailHost {{ background: transparent; }}
#Header     {{ background-color: {HEADER}; border-bottom: 1px solid {RULE_STRONG}; }}
#Panel      {{ background: {PANEL}; border: 1px solid {RULE}; }}
#ReadoutBar {{ background-color: {RAISED}; border-top: 1px solid {RULE_STRONG}; }}
#PathBar    {{ background: {PANEL}; border: 1px solid {RULE}; }}
#Rule       {{ background: {RULE}; }}
#RuleStrong {{ background: {RULE_STRONG}; }}

/* ---- Deslizadores ----------------------------------------------------- */
QSlider::groove:horizontal {{
    height: 2px; background: {RULE_STRONG}; border: none;
}}
QSlider::sub-page:horizontal {{ background: {SIGNAL}; height: 2px; }}
QSlider::handle:horizontal {{
    background: {INK}; border: none;
    width: 3px; height: 13px; margin: -6px 0; border-radius: 1px;
}}
QSlider::handle:horizontal:hover    {{ background: {SIGNAL_HI}; width: 5px; margin: -6px -1px; }}
QSlider::handle:horizontal:pressed  {{ background: {SIGNAL_HI}; }}
QSlider::sub-page:horizontal:disabled {{ background: {RULE}; }}
QSlider::groove:horizontal:disabled   {{ background: {RULE}; }}
QSlider::handle:horizontal:disabled   {{ background: {INK_GHOST}; }}
/* El orden importa: subcontrol y DESPUES pseudo-estado. Al reves
   (`QSlider:focus::handle`) Qt descarta el estilado completo del deslizador y
   la pista desaparece de la pantalla sin dar ningun error. */
QSlider::handle:horizontal:focus      {{ background: {SIGNAL_HI}; width: 5px; margin: -6px -1px; }}

/* ---- Listas desplegables ---------------------------------------------- */
QComboBox {{
    background: {PANEL};
    border: 1px solid {RULE_STRONG};
    padding: 5px 9px;
    color: {INK};
    font-size: 10pt;
    min-height: 17px;
}}
QComboBox:hover    {{ border-color: {INK_FAINT}; }}
QComboBox:focus    {{ border-color: {SIGNAL}; }}
QComboBox:disabled {{ color: {INK_GHOST}; border-color: {RULE}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {INK_DIM};
    margin-right: 7px;
}}
QComboBox QAbstractItemView {{
    background: {RAISED_SOLID};
    border: 1px solid {RULE_STRONG};
    color: {INK};
    selection-background-color: {RAISED_HI};
    selection-color: {SIGNAL_HI};
    outline: none;
    padding: 3px;
}}

/* ---- Campo de texto (h escrita a mano) --------------------------------- */
QLineEdit {{
    background: {PANEL};
    border: 1px solid {RULE_STRONG};
    padding: 5px 8px;
    color: {INK};
    font-size: 10pt;
    selection-background-color: {SIGNAL}; selection-color: #ffffff;
}}
QLineEdit:hover    {{ border-color: {INK_FAINT}; }}
QLineEdit:focus    {{ border-color: {SIGNAL}; }}
QLineEdit:disabled {{ color: {INK_GHOST}; border-color: {RULE}; }}
QLineEdit[invalid="true"] {{ border-color: {CRITICAL}; }}

/* ---- Casillas ---------------------------------------------------------- */
QCheckBox {{ color: {INK_DIM}; font-size: 10pt; spacing: 8px; }}
QCheckBox:hover {{ color: {INK}; }}
QCheckBox:disabled {{ color: {INK_GHOST}; }}
QCheckBox::indicator {{
    width: 12px; height: 12px;
    border: 1px solid {RULE_STRONG};
    background: {PANEL};
}}
QCheckBox::indicator:hover   {{ border-color: {INK_FAINT}; }}
QCheckBox::indicator:checked {{ background: {SIGNAL}; border-color: {SIGNAL}; }}
QCheckBox::indicator:disabled {{ border-color: {RULE}; background: {RAISED_HI}; }}

/* ---- Botones ----------------------------------------------------------- */
QPushButton {{
    background: {PANEL};
    border: 1px solid {RULE_STRONG};
    color: {INK};
    padding: 7px 14px;
    font-size: 10pt;
    font-weight: 500;
}}
QPushButton:hover    {{ background: {RAISED_HI}; border-color: {INK_FAINT}; }}
QPushButton:pressed  {{ background: {RULE}; }}
QPushButton:disabled {{ color: {INK_GHOST}; border-color: {RULE}; background: {RAISED_SOLID}; }}
QPushButton#Primary {{
    background: {SIGNAL}; border-color: {SIGNAL}; color: #ffffff; font-weight: 600;
}}
QPushButton#Primary:hover    {{ background: {SIGNAL_HI}; border-color: {SIGNAL_HI}; }}
QPushButton#Primary:disabled {{ background: {RULE_STRONG}; border-color: {RULE_STRONG}; color: {PANEL}; }}

/* ---- Barras de desplazamiento: superficie del sistema, tambien disenada - */
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {RULE_STRONG}; min-height: 28px; border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {INK_FAINT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {RULE_STRONG}; min-width: 28px; border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {INK_FAINT}; }}

/* ---- Barra de progreso -------------------------------------------------- */
QProgressBar {{
    background: {PANEL}; border: 1px solid {RULE_STRONG};
    height: 3px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {SIGNAL}; }}

/* ---- Texto ---------------------------------------------------------------- */
QTextBrowser, QPlainTextEdit {{
    background: {PANEL}; border: 1px solid {RULE};
    color: {INK_DIM}; selection-background-color: {SIGNAL}; selection-color: #ffffff;
}}
/* El QWidget global fija la sans: el codigo la recupera por nombre. */
QPlainTextEdit#Code {{ font-family: "{MONO}"; font-size: 9pt; border: none; color: {INK}; }}
"""
