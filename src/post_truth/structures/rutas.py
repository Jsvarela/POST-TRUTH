"""Rutas a pie por la ciudad abierta (R8, R13). Sin pygame: las usan la guia G, los transeuntes y el servidor.

ALGORITMO (dos niveles):
1. Grafo: el de la ciudad TAL COMO ESTA AHORA. Una frontera cerrada por una protesta es una arista que no existe, y
   una zona en obras es un vertice que aun no existe, asi que ninguna ruta puede usarlas.
2. Pesos: cada arista pesa lo que se camina de verdad, del centro de una zona al punto de paso de la frontera y de
   ahi al centro de la otra (no la distancia "logica" del grafo). Dijkstra da el minimo SEGUN EL PESO que se le pase.
3. Dijkstra (heapq) da la secuencia de zonas mas corta: O((V + E) log V).
4. Esa secuencia se vuelve puntos: el paso de cada frontera y el centro de cada zona. Entre punto y punto se camina
   en linea recta (los pasos y los centros estan en calle libre).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from post_truth.structures.grafo_ciudad import GrafoCiudad

Punto = tuple[float, float]


@dataclass(frozen=True)
class Geometria:
    """Lo que el mapa aporta a las rutas: el centro de cada zona y el punto de paso de cada frontera."""
    centros: dict[str, Punto]
    pasos: dict[frozenset[str], Punto]

    @classmethod
    def cargar(cls, ruta: str | Path) -> "Geometria":
        """De data/mapa.json (solo JSON: sin imagenes ni ventana)."""
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cls({id: tuple(z["centro"]) for id, z in datos["zonas"].items()},
                   {frozenset((f["desde"], f["hasta"])): tuple(f["paso"]) for f in datos["fronteras"]})

    def paso(self, a: str, b: str) -> Punto | None:
        return self.pasos.get(frozenset((a, b)))


def grafo_de_distancias(grafo: GrafoCiudad, geo: Geometria) -> GrafoCiudad:
    """Copia del grafo (solo sus aristas abiertas) con el peso de cada arista = lo que se camina, en centenas de px."""
    datos = grafo.to_dict()
    for c in datos["conexiones"]:
        p = geo.paso(c["origen"], c["destino"])
        if p is not None:
            a, b = geo.centros[c["origen"]], geo.centros[c["destino"]]
            c["distancia"] = max(1, round((math.dist(a, p) + math.dist(p, b)) / 100))
    return GrafoCiudad.from_dict(datos)


def ruta_puntos(grafo: GrafoCiudad, geo: Geometria, desde: str, hasta: str) -> tuple[tuple[str, ...], list[Punto]]:
    """(zonas de la ruta, puntos a recorrer): Dijkstra sobre las zonas y luego la geometria de cada frontera.
    Sin camino (zona aislada o desconocida): ((), [])."""
    if desde not in grafo or hasta not in grafo:
        return (), []
    ruta = grafo_de_distancias(grafo, geo).ruta(desde, hasta)
    if ruta is None:
        return (), []
    puntos: list[Punto] = []
    for a, b in zip(ruta.zonas, ruta.zonas[1:]):   # cruzar cada frontera y pasar por el centro de la zona
        puntos += [geo.paso(a, b), geo.centros[b]]
    return ruta.zonas, puntos or [geo.centros[hasta]]
