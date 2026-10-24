"""Decorado vivo sobre el mapa por capas: arboles y arbustos en el cesped (lo que no se camina fuera de las zonas),
faroles a los lados de cada calle-frontera y bancas en las zonas. Con semilla fija: siempre el mismo."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from post_truth.mapa_abierto import MapaAbierto

SEMILLA = 2026
MAX_ARBOLES, SEPARACION_ARBOLES = 46, 120
MAX_ARBUSTOS, SEPARACION_ARBUSTOS = 30, 80
MARGEN_BORDE = 30


@dataclass(frozen=True)
class Decorado:
    cesped: tuple[tuple[float, float, int], ...]   # el cesped ya viene pintado en mapa.png
    arboles: tuple[tuple[float, float, float, float], ...]
    arbustos: tuple[tuple[float, float, float, bool], ...]
    faroles: tuple[tuple[float, float, float], ...]
    bancas: tuple[tuple[float, float], ...]


def es_cesped(mapa: MapaAbierto, p: tuple[float, float], margen: float) -> bool:
    """Ni se camina ni es de una zona (asi no tapa calles, edificios ni la fuente), con `margen` alrededor."""
    x, y = p
    ancho, alto = mapa.tamano
    if not (MARGEN_BORDE <= x <= ancho - MARGEN_BORDE and MARGEN_BORDE <= y <= alto - MARGEN_BORDE):
        return False
    for dx, dy in ((0, 0), (-margen, -margen), (margen, -margen), (-margen, margen), (margen, margen)):
        q = (x + dx, y + dy)
        if mapa.zona_en(q) is not None or not mapa.mascara.get_at((int(min(max(q[0], 0), ancho - 1)),
                                                                  int(min(max(q[1], 0), alto - 1)))):
            return False
    return True


def _esparcir(mapa: MapaAbierto, rng: random.Random, maximo: int, separacion: float, margen: float,
              intentos: int = 2500) -> list[tuple[float, float]]:
    puntos: list[tuple[float, float]] = []
    ancho, alto = mapa.tamano
    for _ in range(intentos):
        if len(puntos) >= maximo:
            break
        p = (rng.uniform(0, ancho), rng.uniform(0, alto))
        if es_cesped(mapa, p, margen) and all(math.dist(p, q) >= separacion for q in puntos):
            puntos.append(p)
    return puntos


def generar(mapa: MapaAbierto, semilla: int = SEMILLA) -> Decorado:
    rng = random.Random(semilla)
    arboles = [(*p, rng.uniform(0.8, 1.25), rng.uniform(0, 2 * math.pi))
               for p in _esparcir(mapa, rng, MAX_ARBOLES, SEPARACION_ARBOLES, 40)]
    lejos = [p for p in _esparcir(mapa, rng, MAX_ARBUSTOS * 2, SEPARACION_ARBUSTOS, 20)
             if all(math.dist(p, a[:2]) >= 55 for a in arboles)][:MAX_ARBUSTOS]
    arbustos = [(*p, rng.uniform(0.8, 1.2), rng.random() < 0.3) for p in lejos]
    faroles = []
    for f in mapa.fronteras:   # un farol a cada lado de la calle, junto a su punto de paso
        x, y, w, h = f.calle
        horizontal = f.barrera[2] < f.barrera[3]   # barrera vertical: la calle se cruza en horizontal
        for lado in (-1, 1):
            p = (f.paso[0] + lado * w / 3, y - 18) if horizontal else (x - 18, f.paso[1] + lado * h / 3)
            faroles.append((*p, rng.uniform(0, 2 * math.pi)))
    bancas = [(z.centro[0] + dx, z.centro[1] + 70) for z in mapa.zonas.values() for dx in (-90, 90)]
    return Decorado((), tuple(arboles), tuple(arbustos), tuple(faroles), tuple(bancas))
