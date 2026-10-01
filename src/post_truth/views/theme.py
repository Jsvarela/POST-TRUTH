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


TEMAS = {
    "normal": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (70, 190, 120), (220, 70, 70), (90, 140, 255)),
    "alto_contraste": Tema((0, 0, 0), (255, 255, 255), (20, 20, 20), (255, 255, 0), (255, 0, 255), (0, 255, 255)),
    # Paleta azul/naranja: distinguible con protanopia/deuteranopia
    "daltonismo": Tema((20, 24, 38), (235, 235, 245), (36, 42, 66), (0, 114, 178), (230, 159, 0), (204, 121, 167)),
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
