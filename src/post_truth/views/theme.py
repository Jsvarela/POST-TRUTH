"""Temas visuales: normal, alto contraste y daltonismo."""
from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Tema:
    fondo: Color
    texto: Color
    panel: Color
    bueno: Color
    malo: Color
    acento: Color
    boton: Color
    boton_hover: Color
    boton_texto: Color
    borde: Color
    piel: tuple[Color, Color]
    cabello: tuple[Color, Color]
    rol: tuple[Color, Color, Color, Color]
    cielo: Color
    suelo: Color
    edificio: Color
    verde: Color
    detalle: Color
    boton_off: Color
    texto_off: Color


TEMAS = {
    "normal": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (70, 190, 120), (220, 70, 70), (90, 140, 255),
                   (52, 78, 150), (80, 115, 205), (255, 255, 255), (120, 135, 190),
                   ((240, 200, 165), (150, 105, 75)), ((60, 40, 30), (225, 185, 80)),
                   ((70, 160, 110), (200, 140, 60), (200, 90, 170), (90, 140, 255)),
                   (34, 48, 88), (40, 58, 56), (84, 94, 140), (50, 130, 86), (236, 206, 120),
                   (34, 40, 62), (140, 148, 175)),
    "alto_contraste": Tema((0, 0, 0), (255, 255, 255), (20, 20, 20), (255, 255, 0), (255, 0, 255), (0, 255, 255),
                           (30, 30, 30), (0, 90, 110), (255, 255, 255), (255, 255, 255),
                           ((255, 224, 189), (141, 85, 36)), ((200, 200, 200), (90, 90, 90)),
                           ((0, 255, 0), (255, 255, 0), (255, 0, 255), (0, 200, 255)),
                           (0, 0, 0), (35, 35, 35), (70, 70, 70), (0, 170, 0), (255, 255, 0),
                           (12, 12, 12), (170, 170, 170)),
    "daltonismo": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (0, 114, 178), (230, 159, 0), (204, 121, 167),
                       (0, 85, 135), (0, 114, 178), (255, 255, 255), (120, 135, 190),
                       ((240, 200, 165), (150, 105, 75)), ((60, 40, 30), (240, 228, 66)),
                       ((0, 158, 115), (230, 159, 0), (204, 121, 167), (86, 180, 233)),
                       (30, 44, 84), (62, 58, 46), (84, 94, 140), (0, 120, 92), (240, 228, 66),
                       (34, 40, 62), (140, 148, 175)),
}


def mezclar(a: Color, b: Color, f: float) -> Color:
    """Tono intermedio entre dos colores del tema (asi los matices tambien salen del tema)."""
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


@dataclass(frozen=True)
class Tokens:
    """Medidas del sistema visual, iguales en los tres temas (en pixeles de diseno: se escalan con px())."""
    espacio: tuple[int, ...] = (4, 8, 12, 16, 24, 32)   # xs, s, m, l, xl, xxl
    radio_s: int = 6
    radio_m: int = 10
    radio_l: int = 16
    fuentes: tuple[tuple[str, int, bool], ...] = (("chica", 17, False), ("normal", 22, False),
                                                  ("grande", 30, True), ("titulo", 44, True),
                                                  ("enorme", 72, True))
    alfa_panel: int = 232     # paneles que flotan sobre el mapa
    alfa_velo: int = 150      # velo detras de un modal
    alfa_sombra: int = 90
    dur_rapida: float = 0.15  # segundos
    dur_media: float = 0.3
    dur_lenta: float = 0.6


TOKENS = Tokens()


def esp(nivel: int) -> int:
    """Espaciado del sistema: 0 = xs ... 5 = xxl, ya escalado."""
    from post_truth.config import px
    return px(TOKENS.espacio[nivel])


class GestorTemas:
    """Mantiene el tema activo."""

    def __init__(self) -> None:
        self._orden = list(TEMAS)
        self._i = 0

    @property
    def actual(self) -> Tema:
        return TEMAS[self._orden[self._i]]

    def siguiente(self) -> None:
        self._i = (self._i + 1) % len(self._orden)
