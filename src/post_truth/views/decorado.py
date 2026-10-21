"""Decorado del mundo caminable: cesped, arboles, arbustos, faroles y bancas."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from post_truth.models.mundo import MundoCiudad

SEMILLA = 2026
SEPARACION_CESPED = 95
MAX_ARBOLES, SEPARACION_ARBOLES = 42, 130
MAX_ARBUSTOS, SEPARACION_ARBUSTOS = 28, 90
SEPARACION_FAROLES = 420
MARGEN_BORDE = 30


@dataclass(frozen=True)
class Decorado:
    cesped: tuple[tuple[float, float, int], ...]
    arboles: tuple[tuple[float, float, float, float], ...]
    arbustos: tuple[tuple[float, float, float, bool], ...]
    faroles: tuple[tuple[float, float, float], ...]
    bancas: tuple[tuple[float, float], ...]


def distancia_a_lo_transitable(mundo: MundoCiudad, p: tuple[float, float]) -> float:
    """Que tan lejos queda p del borde de calles y plazas."""
    if mundo.es_transitable(p):
        return 0.0
    return math.dist(p, mundo._corregir(p)) - mundo.radio_jugador


def _libre(mundo: MundoCiudad, p: tuple[float, float], margen: float) -> bool:
    x, y = p
    ancho, alto = mundo.tamano
    if not (MARGEN_BORDE <= x <= ancho - MARGEN_BORDE and MARGEN_BORDE <= y <= alto - MARGEN_BORDE):
        return False
    for e in mundo.edificios:
        ex, ey, ew, eh = e.rect
        if ex - margen <= x <= ex + ew + margen and ey - margen <= y <= ey + eh + margen:
            return False
    return distancia_a_lo_transitable(mundo, p) >= margen


def _esparcir(mundo: MundoCiudad, rng: random.Random, maximo: int, separacion: float, margen: float,
              intentos: int = 1500) -> list[tuple[float, float]]:
    """Puntos al azar sobre el cesped, separados entre si."""
    puntos: list[tuple[float, float]] = []
    ancho, alto = mundo.tamano
    for _ in range(intentos):
        if len(puntos) >= maximo:
            break
        p = (rng.uniform(0, ancho), rng.uniform(0, alto))
        if _libre(mundo, p, margen) and all(math.dist(p, q) >= separacion for q in puntos):
            puntos.append(p)
    return puntos


def generar(mundo: MundoCiudad, semilla: int = SEMILLA) -> Decorado:
    rng = random.Random(semilla)
    ancho, alto = mundo.tamano
    cesped = []
    for gx in range(0, int(ancho), SEPARACION_CESPED):
        for gy in range(0, int(alto), SEPARACION_CESPED):
            p = (gx + rng.uniform(0, SEPARACION_CESPED), gy + rng.uniform(0, SEPARACION_CESPED))
            if _libre(mundo, p, 8):
                cesped.append((*p, rng.randrange(3)))
    arboles = [(*p, rng.uniform(0.8, 1.25), rng.uniform(0, 2 * math.pi))
               for p in _esparcir(mundo, rng, MAX_ARBOLES, SEPARACION_ARBOLES, 48)]
    lejos_de_arboles = [p for p in _esparcir(mundo, rng, MAX_ARBUSTOS * 2, SEPARACION_ARBUSTOS, 22)
                        if all(math.dist(p, a[:2]) >= 55 for a in arboles)][:MAX_ARBUSTOS]
    arbustos = [(*p, rng.uniform(0.8, 1.2), rng.random() < 0.3) for p in lejos_de_arboles]

    faroles = []
    for c in mundo.calles:
        a, b = mundo.plazas[c.desde], mundo.plazas[c.hasta]
        largo = math.dist(a.pos, b.pos)
        ux, uy = (b.pos[0] - a.pos[0]) / largo, (b.pos[1] - a.pos[1]) / largo
        n = max(1, int(largo // SEPARACION_FAROLES))
        for i in range(1, n + 1):
            d = largo * i / (n + 1)
            lado = 1 if i % 2 else -1
            off = c.ancho / 2 + 16
            p = (a.pos[0] + ux * d - uy * off * lado, a.pos[1] + uy * d + ux * off * lado)
            if (math.dist(p, a.pos) > a.radio + 30 and math.dist(p, b.pos) > b.radio + 30
                    and _libre(mundo, p, 4)):
                faroles.append((*p, rng.uniform(0, 2 * math.pi)))

    bancas = []
    for pl in mundo.plazas.values():
        puestas = 0
        for k in range(16):
            ang = 2 * math.pi * k / 16 + 0.2
            p = (pl.pos[0] + math.cos(ang) * (pl.radio + 22), pl.pos[1] + math.sin(ang) * (pl.radio + 22))
            if puestas < 2 and _libre(mundo, p, 6) and all(math.dist(p, q) > 120 for q in bancas):
                bancas.append(p)
                puestas += 1
    return Decorado(tuple(cesped), tuple(arboles), tuple(arbustos), tuple(faroles), tuple(bancas))
