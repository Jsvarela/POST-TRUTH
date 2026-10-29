"""Ciudad abierta (R8): movimiento libre sobre un mapa por capas (assets/mapa/, descrito en data/mapa.json).

- zonas.png: cada zona es un color plano; `zona_en(pos)` dice en que zona esta un punto (None en la calle).
- colisiones.png: negro donde no se camina; se usa con pygame.mask (sin ventana: sirve en pruebas y en un servidor),
  por eso vive fuera de `models/`, que no usa pygame.
- Las barreras son la capa dinamica: una por frontera, activa si su arista NO esta en el grafo de la ciudad.

El GRAFO DE LA CIUDAD SIGUE SIENDO LA FUENTE DE VERDAD aunque el movimiento sea libre: las zonas son sus vertices y
cada frontera (la calle entre dos zonas vecinas) es una arista. El jugador camina donde quiera, pero solo cruza las
fronteras que el grafo tiene abiertas (cerrar una arista levanta su barrera) y las rutas se calculan con Dijkstra
sobre el grafo, a nivel de zonas; el mapa solo aporta la geometria (los puntos de paso de cada frontera).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pygame

from post_truth.structures import rutas
from post_truth.structures.grafo_ciudad import GrafoCiudad

RAIZ = Path(__file__).resolve().parents[2]
PASO = 1 / 120   # sub-pasos del movimiento: igual a 30 y a 60 FPS, y no se "atraviesan" paredes delgadas

Punto = tuple[float, float]


@dataclass(frozen=True)
class ZonaMapa:
    id: str
    nombre: str
    color: tuple[int, int, int]
    centro: Punto
    edificio: tuple[int, int, int, int]
    rect: tuple[int, int, int, int]          # su region (para pintar encima obras, crisis o aislamiento)


@dataclass(frozen=True)
class Frontera:
    desde: str
    hasta: str
    calle: tuple[int, int, int, int]
    barrera: tuple[int, int, int, int]
    paso: Punto

    @property
    def clave(self) -> frozenset[str]:
        return frozenset((self.desde, self.hasta))


def _color(hexa: str) -> tuple[int, int, int]:
    return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))


class MapaAbierto:
    def __init__(self, datos: dict, zonas: pygame.Surface, colisiones: pygame.Surface) -> None:
        self.tamano: tuple[int, int] = tuple(datos["tamano"])
        if zonas.get_size() != self.tamano or colisiones.get_size() != self.tamano:
            raise ValueError("Las capas del mapa deben tener el tamano de data/mapa.json")
        self.zonas = {id: ZonaMapa(id, z["nombre"], _color(z["color"]), tuple(z["centro"]), tuple(z["edificio"]),
                               tuple(z["rect"])) for id, z in datos["zonas"].items()}
        self._por_color = {z.color: z.id for z in self.zonas.values()}
        self.fronteras = [Frontera(f["desde"], f["hasta"], tuple(f["calle"]), tuple(f["barrera"]), tuple(f["paso"]))
                          for f in datos["fronteras"]]
        self.geometria = rutas.Geometria({id: z.centro for id, z in self.zonas.items()},
                                         {f.clave: f.paso for f in self.fronteras})
        self.velocidad = float(datos["velocidad"])
        self.pies = tuple(datos["pies"])
        self.aparicion: Punto = tuple(datos["aparicion"])
        self.imagenes = {k: RAIZ / v for k, v in datos["imagenes"].items()}
        self._zonas = zonas
        # bit encendido = no se camina (negro en colisiones.png)
        self.mascara = pygame.mask.from_threshold(colisiones, (0, 0, 0, 255), (8, 8, 8, 255))
        self._pies = pygame.mask.Mask(self.pies, fill=True)
        self.cerradas: set[frozenset[str]] = set()
        self.jugador: Punto = self.aparicion
        self.ultima_zona = self.zona_en(self.aparicion) or next(iter(self.zonas))
        for id, z in self.zonas.items():
            if self.zona_en(z.centro) != id or self.bloqueado(z.centro):
                raise ValueError(f"El centro de {id} no esta libre dentro de su zona")

    @classmethod
    def cargar(cls, ruta: str | Path) -> "MapaAbierto":
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        imagen = lambda k: pygame.image.load(str(RAIZ / datos["imagenes"][k]))  # noqa: E731
        return cls(datos, imagen("zonas"), imagen("colisiones"))

    # --- consultas ------------------------------------------------------------------------------
    def zona_en(self, p: Punto) -> str | None:
        """La zona bajo `p` segun el color de zonas.png; None en la calle o fuera del mapa."""
        x, y = int(p[0]), int(p[1])
        if not (0 <= x < self.tamano[0] and 0 <= y < self.tamano[1]):
            return None
        return self._por_color.get(tuple(self._zonas.get_at((x, y)))[:3])

    def rect_pies(self, p: Punto) -> pygame.Rect:
        return pygame.Rect(round(p[0] - self.pies[0] / 2), round(p[1] - self.pies[1] / 2), *self.pies)

    def barreras_activas(self) -> list[Frontera]:
        return [f for f in self.fronteras if f.clave in self.cerradas]

    def bloqueado(self, p: Punto) -> bool:
        """Los pies chocan con un muro (mascara pixel a pixel), una barrera o el borde del mapa."""
        r = self.rect_pies(p)
        if r.left < 0 or r.top < 0 or r.right > self.tamano[0] or r.bottom > self.tamano[1]:
            return True
        if self.mascara.overlap(self._pies, r.topleft) is not None:
            return True
        return any(r.colliderect(f.barrera) for f in self.barreras_activas())

    def sincronizar(self, grafo: GrafoCiudad) -> None:
        """Las fronteras abiertas son las aristas que el grafo tiene: las demas levantan su barrera (tambien las de
        una zona que aun no es vertice: esta en obras)."""
        self.cerradas = {f.clave for f in self.fronteras
                         if f.desde not in grafo or f.hasta not in grafo or grafo.distancia(f.desde, f.hasta) is None}

    # --- movimiento -----------------------------------------------------------------------------
    def mover(self, dir_x: float, dir_y: float, dt: float, llegar: Callable[[str], None] | None = None) -> None:
        """8 direcciones (la diagonal no es mas rapida). Se mueve por ejes separados: si un eje choca, el otro sigue,
        y asi el personaje se desliza por las paredes en vez de atascarse."""
        largo = math.hypot(dir_x, dir_y)
        if largo == 0 or dt <= 0:
            return
        ux, uy = dir_x / largo, dir_y / largo
        pasos = max(1, math.ceil(dt / PASO - 1e-9))
        d = self.velocidad * dt / pasos
        for _ in range(pasos):
            x, y = self.jugador
            if not self.bloqueado((x + ux * d, y)):
                x += ux * d
            if not self.bloqueado((x, y + uy * d)):
                y += uy * d
            self.jugador = (x, y)
            zona = self.zona_en(self.jugador)
            if zona is not None and zona != self.ultima_zona:
                self.ultima_zona = zona
                if llegar is not None:
                    llegar(zona)

    def ir_a(self, zona: str) -> None:
        """Pone al jugador en el centro de una zona (al amanecer o al cargar)."""
        self.jugador, self.ultima_zona = self.zonas[zona].centro, zona

    # --- rutas ----------------------------------------------------------------------------------
    def frontera(self, a: str, b: str) -> Frontera | None:
        return next((f for f in self.fronteras if f.clave == frozenset((a, b))), None)

    def grafo_de_distancias(self, grafo: GrafoCiudad) -> GrafoCiudad:
        """Pesos = lo que se camina (structures/rutas.py explica el algoritmo)."""
        return rutas.grafo_de_distancias(grafo, self.geometria)

    def ruta_puntos(self, grafo: GrafoCiudad, desde: str, hasta: str) -> tuple[tuple[str, ...], list[Punto]]:
        """(zonas de la ruta, puntos de paso): Dijkstra sobre las zonas y luego la geometria de cada frontera."""
        return rutas.ruta_puntos(grafo, self.geometria, desde, hasta)
