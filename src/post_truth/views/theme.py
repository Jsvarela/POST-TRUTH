"""Temas visuales (accesibilidad): normal, alto contraste y daltonismo."""
from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Tema:
    fondo: Color
    texto: Color
    panel: Color
    bueno: Color   # indicador sano / informacion verificada
    malo: Color    # peligro / desinformacion
    acento: Color
    # Botones: el texto es igual en reposo y hover; solo cambia el relleno (y el borde).
    boton: Color
    boton_hover: Color
    boton_texto: Color
    borde: Color
    # Personajes: dos tonos de piel y de cabello (el id de apariencia elige uno) y un
    # color de ropa por rol, en el orden de `list(Role)` (ciudadano, periodista, influencer, candidato).
    piel: tuple[Color, Color]
    cabello: tuple[Color, Color]
    rol: tuple[Color, Color, Color, Color]


TEMAS = {
    "normal": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (70, 190, 120), (220, 70, 70), (90, 140, 255),
                   (52, 78, 150), (80, 115, 205), (255, 255, 255), (120, 135, 190),
                   ((240, 200, 165), (150, 105, 75)), ((60, 40, 30), (225, 185, 80)),
                   ((70, 160, 110), (200, 140, 60), (200, 90, 170), (90, 140, 255))),
    "alto_contraste": Tema((0, 0, 0), (255, 255, 255), (20, 20, 20), (255, 255, 0), (255, 0, 255), (0, 255, 255),
                           (30, 30, 30), (0, 90, 110), (255, 255, 255), (255, 255, 255),
                           ((255, 224, 189), (141, 85, 36)), ((200, 200, 200), (90, 90, 90)),
                           ((0, 255, 0), (255, 255, 0), (255, 0, 255), (0, 200, 255))),
    # Paleta azul/naranja: distinguible con protanopia/deuteranopia
    "daltonismo": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (0, 114, 178), (230, 159, 0), (204, 121, 167),
                       (0, 85, 135), (0, 114, 178), (255, 255, 255), (120, 135, 190),
                       ((240, 200, 165), (150, 105, 75)), ((60, 40, 30), (240, 228, 66)),
                       ((0, 158, 115), (230, 159, 0), (204, 121, 167), (86, 180, 233))),
}


class GestorTemas:
    """Mantiene el tema activo; las vistas leen `gestor.actual`."""

    def __init__(self) -> None:
        self._orden = list(TEMAS)
        self._i = 0

    @property
    def actual(self) -> Tema:
        return TEMAS[self._orden[self._i]]

    def siguiente(self) -> None:
        self._i = (self._i + 1) % len(self._orden)
