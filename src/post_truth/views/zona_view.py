"""Fondos de escena, uno por zona de la ciudad, dibujados con formas de Pygame (sin imagenes).

Cada zona se reconoce por su silueta (colegio con bandera, casas, arboles, fuente, edificio
con columnas y reloj) y no solo por el color, y todos los colores salen del tema activo para
mantener alto contraste y daltonismo. Todo se dibuja con fracciones del rectangulo recibido,
asi escala con cualquier tamano. Para cambiarlo por PNG de assets/ basta reemplazar esta
funcion; el modelo solo conoce el id de la zona.
"""
from typing import Callable

import pygame

from post_truth.views.theme import Tema

Pintor = Callable[[pygame.Surface, Tema, pygame.Rect, int], None]
HORIZONTE = 0.80  # fraccion del alto donde termina el cielo y empieza el suelo


def dibujar_fondo_zona(pantalla: pygame.Surface, zona_id: str, tema: Tema, rect: pygame.Rect) -> None:
    """Cielo, suelo y los elementos propios de la zona. Una zona desconocida queda con cielo y suelo."""
    horizonte = rect.y + round(rect.height * HORIZONTE)
    pygame.draw.rect(pantalla, tema.cielo, (rect.x, rect.y, rect.width, horizonte - rect.y))
    pygame.draw.rect(pantalla, tema.suelo, (rect.x, horizonte, rect.width, rect.bottom - horizonte))
    pintor = _PINTORES.get(zona_id)
    if pintor:
        pintor(pantalla, tema, rect, horizonte)


def _ventanas(pantalla: pygame.Surface, tema: Tema, x: int, y: int, filas: int, columnas: int,
              paso: int, lado: int) -> None:
    for f in range(filas):
        for c in range(columnas):
            pygame.draw.rect(pantalla, tema.detalle, (x + c * paso, y + f * paso, lado, lado), border_radius=2)


def _colegio(p: pygame.Surface, t: Tema, r: pygame.Rect, h: int) -> None:
    u = r.height / 100  # unidad: 1% del alto
    for x0, ancho in ((0.03, 0.30), (0.60, 0.34)):
        x, w = r.x + round(x0 * r.width), round(ancho * r.width)
        alto = round(52 * u)
        pygame.draw.rect(p, t.edificio, (x, h - alto, w, alto))
        pygame.draw.rect(p, t.borde, (x, h - alto, w, alto), 2)
        _ventanas(p, t, x + round(w * 0.08), h - alto + round(8 * u), 2, 4, round(w * 0.22), round(w * 0.12))
        pygame.draw.rect(p, t.suelo, (x + w // 2 - round(w * 0.06), h - round(16 * u), round(w * 0.12), round(16 * u)))
    # Mastil con bandera sobre el edificio de la izquierda
    mx = r.x + round(0.18 * r.width)
    pygame.draw.line(p, t.texto, (mx, h - round(52 * u)), (mx, h - round(74 * u)), 3)
    pygame.draw.polygon(p, t.acento, [(mx, h - round(74 * u)), (mx + round(36 * u), h - round(68 * u)),
                                      (mx, h - round(62 * u))])
    # Reja del patio
    for i in range(14):
        x = r.x + round((0.36 + i * 0.017) * r.width)
        pygame.draw.line(p, t.borde, (x, h - round(10 * u)), (x, h), 2)


def _barrio(p: pygame.Surface, t: Tema, r: pygame.Rect, h: int) -> None:
    u = r.height / 100
    casas = [(0.02, 0.15, 30), (0.19, 0.13, 38), (0.36, 0.16, 26), (0.58, 0.14, 40), (0.76, 0.17, 32)]
    for x0, ancho, alto in casas:
        x, w, a = r.x + round(x0 * r.width), round(ancho * r.width), round(alto * u)
        pygame.draw.rect(p, t.edificio, (x, h - a, w, a))
        pygame.draw.polygon(p, t.borde, [(x - 6, h - a), (x + w + 6, h - a), (x + w // 2, h - a - round(16 * u))])
        _ventanas(p, t, x + round(w * 0.18), h - a + round(6 * u), 1, 2, round(w * 0.38), round(w * 0.22))
        pygame.draw.rect(p, t.suelo, (x + w // 2 - 6, h - round(10 * u), 12, round(10 * u)))
    pygame.draw.circle(p, t.detalle, (r.x + round(0.9 * r.width), r.y + round(16 * u)), round(8 * u))  # luna


def _parque(p: pygame.Surface, t: Tema, r: pygame.Rect, h: int) -> None:
    u = r.height / 100
    pygame.draw.circle(p, t.detalle, (r.x + round(0.84 * r.width), r.y + round(18 * u)), round(10 * u))  # sol
    for x0, escala in ((0.04, 1.0), (0.26, 0.8), (0.60, 1.1), (0.86, 0.9)):
        x = r.x + round(x0 * r.width)
        tronco = round(24 * u * escala)
        pygame.draw.rect(p, t.edificio, (x - 5, h - tronco, 10, tronco))
        for dx, dy, rad in ((0, 0, 18), (-14, 8, 14), (14, 8, 14)):
            pygame.draw.circle(p, t.verde, (x + round(dx * escala), h - tronco - round(dy * escala)),
                               round(rad * u * escala * 0.9))
    # Banca
    bx = r.x + round(0.44 * r.width)
    pygame.draw.rect(p, t.edificio, (bx, h - round(12 * u), round(0.09 * r.width), round(4 * u)))
    pygame.draw.rect(p, t.edificio, (bx + 4, h - round(8 * u), 5, round(8 * u)))
    pygame.draw.rect(p, t.edificio, (bx + round(0.09 * r.width) - 9, h - round(8 * u), 5, round(8 * u)))


def _plaza(p: pygame.Surface, t: Tema, r: pygame.Rect, h: int) -> None:
    u = r.height / 100
    for x0, ancho, alto in ((0.02, 0.18, 44), (0.22, 0.12, 30), (0.70, 0.14, 36), (0.86, 0.12, 48)):
        pygame.draw.rect(p, t.edificio, (r.x + round(x0 * r.width), h - round(alto * u),
                                         round(ancho * r.width), round(alto * u)))
    # Baldosas del suelo: lineas que convergen al horizonte (perspectiva simple)
    for i in range(0, 13):
        x = r.x + round(i / 12 * r.width)
        pygame.draw.line(p, t.edificio, (x, r.bottom), (r.x + r.width // 2 + (x - r.x - r.width // 2) // 3, h), 1)
    # Fuente central
    cx, cy = r.x + r.width // 2, h + round(8 * u)
    pygame.draw.ellipse(p, t.edificio, (cx - round(15 * u), cy - round(5 * u), round(30 * u), round(9 * u)))
    pygame.draw.ellipse(p, t.acento, (cx - round(12 * u), cy - round(3 * u), round(24 * u), round(6 * u)))
    pygame.draw.line(p, t.edificio, (cx, cy), (cx, cy - round(14 * u)), 4)
    for dx in (-10, 0, 10):
        pygame.draw.line(p, t.acento, (cx, cy - round(14 * u)), (cx + round(dx * u), cy - round(4 * u)), 2)
    # Faroles
    for x0 in (0.30, 0.68):
        x = r.x + round(x0 * r.width)
        pygame.draw.line(p, t.texto, (x, h + round(6 * u)), (x, h - round(26 * u)), 3)
        pygame.draw.circle(p, t.detalle, (x, h - round(28 * u)), round(4 * u))


def _alcaldia(p: pygame.Surface, t: Tema, r: pygame.Rect, h: int) -> None:
    u = r.height / 100
    x0, w = r.x + round(0.30 * r.width), round(0.40 * r.width)
    alto = round(48 * u)
    pygame.draw.rect(p, t.edificio, (x0, h - alto, w, alto))
    # Frontis triangular con reloj
    pygame.draw.polygon(p, t.borde, [(x0 - 8, h - alto), (x0 + w + 8, h - alto), (x0 + w // 2, h - alto - round(22 * u))])
    reloj = (x0 + w // 2, h - alto - round(8 * u))
    pygame.draw.circle(p, t.detalle, reloj, round(7 * u))
    pygame.draw.line(p, t.fondo, reloj, (reloj[0], reloj[1] - round(5 * u)), 2)
    pygame.draw.line(p, t.fondo, reloj, (reloj[0] + round(4 * u), reloj[1]), 2)
    # Columnas y escalinata
    for i in range(6):
        cx = x0 + round(w * (0.08 + i * 0.168))
        pygame.draw.rect(p, t.texto, (cx - 4, h - alto + round(4 * u), 8, alto - round(10 * u)))
    for i in range(3):
        pygame.draw.rect(p, t.edificio, (x0 - i * 8, h - round((3 - i) * 3 * u), w + i * 16, round(3 * u)))
    # Banderas a los lados
    for fx in (x0 - round(0.05 * r.width), x0 + w + round(0.05 * r.width)):
        pygame.draw.line(p, t.texto, (fx, h), (fx, h - round(46 * u)), 3)
        pygame.draw.polygon(p, t.acento, [(fx, h - round(46 * u)), (fx + round(18 * u), h - round(41 * u)),
                                          (fx, h - round(36 * u))])


_PINTORES: dict[str, Pintor] = {
    "colegio": _colegio, "barrio": _barrio, "parque": _parque, "plaza": _plaza, "alcaldia": _alcaldia,
}
