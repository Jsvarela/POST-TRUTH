"""Sprites pixel art originales, construidos en codigo pixel a pixel (sin assets de terceros).

Personajes: cuadros de 16x24 pixeles de arte en 4 direcciones (idle de 2 cuadros, caminar de 4). Se pintan con
"claves" (piel, pelo, ropa...) y al final cada clave toma su color del tema activo, asi que los temas de alto
contraste y daltonismo siguen funcionando: el color de la ropa sigue diciendo el rol. El contorno se calcula solo
(todo pixel vacio pegado a uno pintado), como en el pixel art hecho a mano.

Decorado: arboles, arbustos, faroles y bancas con la misma luz (arriba a la izquierda) y el mismo contorno.

Todo se cachea por (clave, escala): se construye una vez y luego solo se copia.
"""
from __future__ import annotations

import random

import pygame

from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.theme import BLANCO, NEGRO, OSCURO_CALIDO, OSCURO_FRIO, PALETA_DECORADO, Tema, mezclar

ANCHO, ALTO = 16, 24
_ROLES = list(Role)
_CACHE: dict = {}


def _tono(c, f: float) -> tuple[int, int, int]:
    """f < 1 oscurece, f > 1 aclara hacia el blanco."""
    if f <= 1:
        return tuple(max(0, round(v * f)) for v in c)
    return tuple(min(255, round(v + (255 - v) * (f - 1))) for v in c)


class Rejilla:
    """Rejilla de claves de color: lo que se pinta antes de saber el tema."""

    def __init__(self, w: int = ANCHO, h: int = ALTO) -> None:
        self.w, self.h = w, h
        self.g: list[list[str | None]] = [[None] * w for _ in range(h)]

    def p(self, x: int, y: int, k: str | None) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = k

    def r(self, x: int, y: int, w: int, h: int, k: str | None) -> None:
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.p(i, j, k)

    def get(self, x: int, y: int) -> str | None:
        return self.g[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def contorno(self) -> None:
        nuevos = []
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] is None and any(self.get(x + dx, y + dy) not in (None, "O")
                                                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    nuevos.append((x, y))
        for x, y in nuevos:
            self.g[y][x] = "O"

    def superficie(self, colores: dict[str, tuple[int, int, int]]) -> pygame.Surface:
        sup = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y, fila in enumerate(self.g):
            for x, k in enumerate(fila):
                if k is not None:
                    sup.set_at((x, y), colores[k])
        return sup


# ---------------------------------------------------------------------------------------------------------------
# Personajes
# ---------------------------------------------------------------------------------------------------------------
def _colores_personaje(p: Personaje, tema: Tema) -> dict[str, tuple[int, int, int]]:
    piel, pelo = tema.piel[p.apariencia], tema.cabello[p.apariencia]
    ropa = tema.rol[_ROLES.index(p.rol)]
    contorno = _tono(mezclar(tema.fondo, NEGRO, 0.4), 0.8)
    pantalon = mezclar(tema.edificio, tema.fondo, 0.45) if p.rol is not Role.CANDIDATE else _tono(ropa, 0.55)
    return {
        "O": contorno, "S": piel, "s": _tono(piel, 0.82), "E": _tono(mezclar(tema.fondo, NEGRO, 0.5), 0.7),
        "M": _tono(piel, 0.6), "H": pelo, "h": _tono(pelo, 0.72), "L": _tono(pelo, 1.35),
        "C": ropa, "c": _tono(ropa, 0.74), "l": _tono(ropa, 1.25),
        "P": pantalon, "p": _tono(pantalon, 0.75), "B": _tono(mezclar(tema.fondo, OSCURO_CALIDO, 0.5), 0.9),
        "A": tema.acento, "a": _tono(tema.acento, 0.72), "W": mezclar(tema.texto, BLANCO, 0.5),
        "K": _tono(mezclar(tema.fondo, OSCURO_FRIO, 0.5), 0.8), "T": tema.malo, "t": _tono(tema.malo, 0.75),
        "X": mezclar(tema.acento, BLANCO, 0.55),
    }


def _piernas_frente(g: Rejilla, y0: int, cuadro: int, caminando: bool) -> None:
    """Piernas de frente o de espaldas: en el paso una se alza un pixel."""
    alza_izq = 1 if caminando and cuadro == 1 else 0
    alza_der = 1 if caminando and cuadro == 3 else 0
    g.r(5, y0, 6, 1, "P")
    for x, alza in ((5, alza_izq), (9, alza_der)):
        fondo = 21 - alza
        g.r(x, y0, 2, fondo - y0, "P")
        g.p(x + 1, fondo - 1, "p")
        g.r(x, fondo, 2, 1, "B")
    g.p(7, y0, "p")
    g.p(8, y0, "p")


def _cabeza_frente(g: Rejilla, y: int, mujer: bool, espalda: bool, animo: int) -> None:
    g.r(4, y, 8, 1, "S")
    g.r(3, y + 1, 10, 7, "S")
    g.r(4, y + 8, 8, 1, "S")
    g.r(12, y + 2, 1, 6, "s")
    g.r(4, y + 8, 8, 1, "s")
    # pelo
    g.r(4, y - 1, 8, 1, "H")
    g.r(3, y, 10, 2, "H")
    g.p(5, y, "L")
    g.p(6, y, "L")
    if espalda:
        g.r(3, y + 2, 10, 6, "H")
        g.r(4, y + 8, 8, 1, "h")
        g.r(11, y + 2, 2, 6, "h")
    else:
        g.r(3, y + 2, 1, 3, "H")
        g.r(12, y + 2, 1, 3, "h")
        g.r(4, y + 2, 3, 1, "H")       # flequillo
        g.r(9, y + 2, 3, 1, "H")
        g.p(4, y + 3, "H")
        g.r(5, y + 4, 1, 2, "E")       # ojos de dos pixeles
        g.r(10, y + 4, 1, 2, "E")
        g.p(4, y + 6, "s")             # mejillas
        g.p(11, y + 6, "s")
        if animo > 0:
            g.r(7, y + 7, 2, 1, "M")
            g.p(6, y + 6, "M")
            g.p(9, y + 6, "M")
        elif animo < 0:
            g.r(7, y + 6, 2, 1, "M")
            g.p(6, y + 7, "M")
            g.p(9, y + 7, "M")
        else:
            g.r(7, y + 7, 2, 1, "M")
    if mujer:
        largo = 10 if espalda else 9
        g.r(2, y + 1, 1, largo, "H")
        g.r(13, y + 1, 1, largo, "h")
        if espalda:
            g.r(3, y + 8, 10, 3, "H")
            g.r(10, y + 8, 3, 3, "h")
        else:
            g.r(3, y + 5, 1, 5, "H")
            g.r(12, y + 5, 1, 5, "h")


def _torso_frente(g: Rejilla, y: int, cuadro: int, caminando: bool, espalda: bool) -> None:
    g.r(7, y - 1, 2, 1, "s")   # cuello
    g.r(4, y, 8, 6, "C")
    g.r(11, y, 1, 6, "c")
    g.r(4, y + 5, 8, 1, "c")
    g.r(5, y, 2, 1, "l")
    # brazos (se balancean al caminar)
    for x, signo in ((2, 1), (12, -1)):
        balanceo = 0
        if caminando:
            balanceo = (1 if cuadro == 1 else -1 if cuadro == 3 else 0) * signo
        largo = 5 + balanceo
        g.r(x, y, 2, largo, "C")
        g.p(x + (1 if x == 2 else 0), y + largo - 1, "c")
        g.r(x, y + largo, 2, 1, "S")


def _frente(p: Personaje, cuadro: int, caminando: bool, espalda: bool, animo: int = 0) -> Rejilla:
    g = Rejilla()
    mujer = p.genero is Genero.MUJER
    bob = -1 if caminando and cuadro in (1, 3) else (1 if not caminando and cuadro == 1 else 0)
    cy = 3 + bob
    ty = cy + 10
    _piernas_frente(g, ty + 6, cuadro, caminando)
    if mujer and espalda:
        _cabeza_frente(g, cy, mujer, espalda, animo)
        _torso_frente(g, ty, cuadro, caminando, espalda)
        g.r(3, cy + 8, 10, 3, "H")   # el pelo cae sobre la espalda
        g.r(10, cy + 8, 3, 3, "h")
    else:
        _torso_frente(g, ty, cuadro, caminando, espalda)
        _cabeza_frente(g, cy, mujer, espalda, animo)
    _accesorio_frente(g, p.rol, cy, ty, espalda, cuadro, caminando)
    g.contorno()
    return g


def _accesorio_frente(g: Rejilla, rol: Role, cy: int, ty: int, espalda: bool, cuadro: int,
                      caminando: bool) -> None:
    if rol is Role.CITIZEN:   # gorra con visera
        g.r(3, cy - 2, 10, 3, "A")
        g.r(4, cy - 2, 3, 1, "X")
        g.r(3, cy, 10, 1, "a")
        if not espalda:
            g.r(4, cy + 1, 8, 1, "a")
    elif rol is Role.JOURNALIST:   # gafas y credencial de prensa
        if not espalda:
            for x0 in (4, 9):   # monturas alrededor de cada ojo
                g.r(x0, cy + 3, 3, 1, "K")
                g.r(x0, cy + 4, 1, 2, "K")
                g.r(x0 + 2, cy + 4, 1, 2, "K")
                g.r(x0 + 1, cy + 6, 1, 1, "s")
            g.r(7, cy + 4, 2, 1, "K")
            g.p(6, ty, "W")
            g.p(9, ty, "W")
            g.r(7, ty + 1, 2, 1, "W")
            g.r(7, ty + 2, 2, 2, "W")
            g.p(8, ty + 3, "A")
        else:
            g.r(4, cy + 3, 8, 1, "K")
    elif rol is Role.INFLUENCER:   # audifonos y telefono en la mano
        g.r(4, cy - 2, 8, 1, "K")
        g.p(3, cy - 1, "K")
        g.p(12, cy - 1, "K")
        g.r(2, cy + 1, 2, 3, "A")
        g.r(12, cy + 1, 2, 3, "a")
        if not espalda:
            mano = ty + 5 + ((-1 if cuadro == 1 else 1 if cuadro == 3 else 0) if caminando else 0)
            g.r(12, mano - 1, 2, 3, "K")
            g.p(12, mano - 1, "X")
    else:   # candidato: saco, camisa y corbata
        if not espalda:
            g.r(7, ty, 2, 4, "W")
            g.r(7, ty + 1, 2, 3, "T")
            g.p(8, ty + 3, "t")
            g.p(6, ty, "c")
            g.p(9, ty, "c")


def _lado(p: Personaje, cuadro: int, caminando: bool) -> Rejilla:
    """De perfil, mirando a la derecha (la izquierda es el espejo)."""
    g = Rejilla()
    mujer = p.genero is Genero.MUJER
    bob = -1 if caminando and cuadro in (1, 3) else (1 if not caminando and cuadro == 1 else 0)
    cy = 3 + bob
    ty = cy + 10
    ly = ty + 6
    # piernas: una adelante y otra atras
    paso = (2 if cuadro == 1 else -2 if cuadro == 3 else 0) if caminando else 0
    g.r(6, ly, 4, 1, "P")
    for dx, k in ((-paso, "p"), (paso, "P")):
        x = 7 + dx // 2
        alto_p = 21 - ly - (1 if dx != 0 and k == "p" else 0)
        g.r(x, ly, 2, alto_p, k)
        g.r(x + (1 if k == "P" else 0), ly + alto_p, 2, 1, "B")
    # brazo de atras, torso y brazo de adelante
    g.r(6, ty, 5, 6, "C")
    g.r(10, ty, 1, 6, "c")
    g.r(6, ty + 5, 5, 1, "c")
    g.p(7, ty, "l")
    g.r(7, ty - 1, 2, 1, "s")
    brazo = (-paso // 2) if caminando else 0
    g.r(8 + brazo, ty + 1, 2, 4, "c" if p.rol is Role.CANDIDATE else "C")
    g.r(8 + brazo, ty + 5, 2, 1, "S")
    # cabeza de perfil
    g.r(5, cy, 7, 1, "S")
    g.r(4, cy + 1, 9, 7, "S")
    g.r(5, cy + 8, 7, 1, "s")
    g.p(13, cy + 5, "S")   # nariz
    g.r(10, cy + 4, 1, 2, "E")
    g.r(11, cy + 7, 1, 1, "M")
    g.r(5, cy - 1, 7, 1, "H")
    g.r(4, cy, 8, 2, "H")
    g.r(4, cy + 2, 4, 4, "H")
    g.r(4, cy + 6, 2, 2, "h")
    g.r(8, cy + 2, 3, 1, "H")
    g.p(6, cy, "L")
    g.p(7, cy, "L")
    g.p(7, cy + 4, "s")   # oreja
    if mujer:
        g.r(3, cy + 1, 2, 10, "H")
        g.r(5, cy + 8, 1, 3, "h")
    # accesorio
    if p.rol is Role.CITIZEN:
        g.r(4, cy - 2, 8, 3, "A")
        g.r(5, cy - 2, 3, 1, "X")
        g.r(11, cy, 4, 1, "a")
    elif p.rol is Role.JOURNALIST:
        g.r(9, cy + 3, 3, 1, "K")
        g.r(6, cy + 3, 3, 1, "K")
        g.p(11, ty + 1, "W")
        g.p(11, ty + 2, "W")
    elif p.rol is Role.INFLUENCER:
        g.r(5, cy - 2, 6, 1, "K")
        g.p(4, cy - 1, "K")
        g.r(6, cy + 2, 3, 3, "A")
        g.r(9 + brazo, ty + 4, 2, 2, "K")
    else:
        g.r(10, ty, 1, 3, "W")
        g.p(10, ty + 1, "T")
        g.p(10, ty + 2, "T")
    g.contorno()
    return g


def cuadro_personaje(p: Personaje, tema: Tema, animacion: str, cuadro: int, escala: int,
                     animo: int = 0) -> pygame.Surface:
    """Superficie (ya escalada) de la animacion `animacion` (p. ej. "caminar_izquierda") en su `cuadro`."""
    clave = ("pj", p, id(tema), animacion, cuadro, escala, animo)
    if clave in _CACHE:
        return _CACHE[clave]
    estado, direccion = animacion.split("_", 1)
    caminando = estado == "caminar"
    if direccion in ("izquierda", "derecha"):
        g = _lado(p, cuadro, caminando)
    else:
        g = _frente(p, cuadro, caminando, espalda=direccion == "arriba", animo=animo)
    sup = g.superficie(_colores_personaje(p, tema))
    if direccion == "izquierda":
        sup = pygame.transform.flip(sup, True, False)
    sup = pygame.transform.scale_by(sup, escala)
    _CACHE[clave] = sup
    return sup


def sombra(ancho: int, alto: int, alfa: int = 90) -> pygame.Surface:
    clave = ("sombra", ancho, alto, alfa)
    if clave not in _CACHE:
        s = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (10, 12, 20, alfa), s.get_rect())
        _CACHE[clave] = s
    return _CACHE[clave]


# ---------------------------------------------------------------------------------------------------------------
# Decorado
# ---------------------------------------------------------------------------------------------------------------


def _copa(g: Rejilla, circulos, semilla: int) -> None:
    """Copa como union de circulos, sombreada por pixel con la luz arriba a la izquierda."""
    rng = random.Random(semilla)
    cx = sum(c[0] for c in circulos) / len(circulos)
    cy = sum(c[1] for c in circulos) / len(circulos)
    radio = max(c[2] for c in circulos) * 1.6
    for y in range(g.h):
        for x in range(g.w):
            if not any((x - a) ** 2 + (y - b) ** 2 <= r * r for a, b, r in circulos):
                continue
            luz = ((x - cx) + (y - cy) * 1.2) / radio + rng.uniform(-0.18, 0.18)
            k = "3" if luz < -0.62 else "2" if luz < -0.15 else "1" if luz < 0.45 else "0"
            g.p(x, y, k)
    for _ in range(len(circulos) * 6):   # hojitas sueltas
        a, b, r = rng.choice(circulos)
        x, y = round(a + rng.uniform(-r, r) * 0.7), round(b + rng.uniform(-r, r) * 0.7)
        if g.get(x, y) in ("1", "2"):
            g.p(x, y, "0" if g.get(x, y) == "1" else "1")


def _colores_deco() -> dict[str, tuple[int, int, int]]:
    return PALETA_DECORADO   # hojas (sombra, base, luz, brillo), tronco, contorno, flores, madera, metal, luz


def arbol(variante: int, mover: int, escala: int) -> pygame.Surface:
    """Arbol de 22x30 pixeles de arte; `mover` desplaza la copa (viento) -1, 0 o 1."""
    clave = ("arbol", variante, mover, escala)
    if clave not in _CACHE:
        g = Rejilla(24, 32)
        g.r(10, 18, 4, 11, "T")
        g.r(12, 18, 2, 11, "t")
        g.p(9, 28, "T")
        g.p(14, 28, "t")
        formas = (((12, 10, 8), (7, 14, 5), (17, 14, 5)),                 # (x, y, radio): no es un color
                  ((12, 9, 7), (8, 13, 6), (16, 13, 6), (12, 16, 6)),     # no es un color
                  ((12, 11, 9), (6, 15, 4), (18, 16, 4)))[variante % 3]  # no es un color
        _copa(g, tuple((a + mover, b, r) for a, b, r in formas), semilla=variante * 7 + 1)
        g.contorno()
        _CACHE[clave] = pygame.transform.scale_by(g.superficie(_colores_deco()), escala)
    return _CACHE[clave]


def arbusto(flores: bool, escala: int) -> pygame.Surface:
    clave = ("arbusto", flores, escala)
    if clave not in _CACHE:
        g = Rejilla(16, 11)
        _copa(g, ((5, 6, 4), (10, 6, 4), (8, 4, 4)), semilla=5)   # circulos (x, y, radio): no es un color
        if flores:
            for x, y, k in ((5, 4, "F"), (9, 3, "f"), (11, 6, "F"), (7, 7, "f")):
                g.p(x, y, k)
        g.contorno()
        _CACHE[clave] = pygame.transform.scale_by(g.superficie(_colores_deco()), escala)
    return _CACHE[clave]


def farol(encendido: bool, escala: int) -> pygame.Surface:
    clave = ("farol", encendido, escala)
    if clave not in _CACHE:
        g = Rejilla(9, 26)
        g.r(4, 6, 1, 18, "K")
        g.p(3, 6, "k")
        g.r(3, 23, 3, 2, "k")
        g.r(2, 1, 5, 5, "k")
        g.r(3, 2, 3, 3, "Y" if encendido else "y")
        g.p(3, 2, "Y")
        g.r(1, 1, 7, 1, "K")
        g.contorno()
        _CACHE[clave] = pygame.transform.scale_by(g.superficie(_colores_deco()), escala)
    return _CACHE[clave]


def banca(escala: int) -> pygame.Surface:
    clave = ("banca", escala)
    if clave not in _CACHE:
        g = Rejilla(18, 11)
        g.r(1, 1, 16, 2, "M")
        g.r(1, 2, 16, 1, "m")
        g.r(1, 5, 16, 3, "M")
        g.r(1, 7, 16, 1, "m")
        for x in (2, 15):
            g.r(x, 3, 1, 2, "k")
            g.r(x, 8, 1, 2, "k")
        g.contorno()
        _CACHE[clave] = pygame.transform.scale_by(g.superficie(_colores_deco()), escala)
    return _CACHE[clave]
