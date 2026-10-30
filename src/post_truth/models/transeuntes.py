"""Transeuntes (R13, L2): ciudadanos del grafo social que caminan por la ciudad abierta de zona en zona, como
ambiente. Solo los personajes del dia (data/historia.json: los testigos de la noticia y quien tiene algo que decir)
llevan marca y se puede hablar con ellos manteniendo E; los demas solo pasan.
shortcut: el rumor por transeunte y su persuasion (models/persuasion.py) quedan en el codigo pero nadie sale con
rumor desde L2; L4 decide si vuelven como personajes de la historia o se borran.

RUTAS: cada transeunte elige un destino entre las zonas que puede alcanzar (BFS `saltos` sobre el grafo de la
ciudad, O(V + E)) y va por el camino mas corto a pie (Dijkstra sobre las distancias reales, structures/rutas.py).
Si se cierra una frontera que le falta cruzar, recalcula desde la zona donde esta; si su zona queda aislada, espera.
Logica pura y serializable: la usa la sesion (y por ella el servidor) sin ventana.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from post_truth.config import RUTA_MAPA, RUTA_TRANSEUNTES
from post_truth.structures import rutas
from post_truth.structures.grafo_ciudad import GrafoCiudad


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_TRANSEUNTES.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def geometria() -> rutas.Geometria:
    return rutas.Geometria.cargar(RUTA_MAPA)


@dataclass
class Transeunte:
    id: str
    nombre: str
    rol: str                         # Role.name
    zona: str
    pos: list[float]
    zonas: list[str] = field(default_factory=list)          # la ruta que le queda; zonas[0] es donde esta
    puntos: list[list[float]] = field(default_factory=list)  # pasos de frontera y centros por recorrer
    espera: float = 0.0              # parado: llego a un destino o no tiene a donde ir
    rumor: str | None = None
    testigo: str | None = None       # id de la evidencia (TESTIGO) de la noticia actual que cuenta
    enojado: float = 0.0             # segundos en que no quiere hablar
    regado: bool = False             # ya solto su rumor hoy (uno por dia: no dispara solo las crisis de zona)
    dice: str | None = None          # personaje de la historia de hoy: lo que cuenta si se lo escucha

    @property
    def interesa(self) -> bool:
        return (self.rumor is not None or self.testigo is not None or self.dice is not None) and self.enojado <= 0


class Calle:
    def __init__(self, transeuntes: list[Transeunte], semilla: int) -> None:
        self.transeuntes = transeuntes
        self.rng = random.Random(semilla)

    @classmethod
    def crear(cls, ciudadanos: list, mapa: GrafoCiudad, semilla: int, propios: set[str]) -> "Calle":
        """`ciudadanos`: los del grafo social; se eligen los que viven en una zona abierta y no son jugadores."""
        calle = cls([], semilla)
        candidatos = sorted((c for c in ciudadanos if c.id not in propios and c.zona in mapa), key=lambda c: c.id)
        geo = geometria()
        for c in calle.rng.sample(candidatos, min(datos()["cantidad"], len(candidatos))):
            calle.transeuntes.append(Transeunte(c.id, c.nombre, c.rol.name, c.zona, list(geo.centros[c.zona])))
        return calle

    def poner_testigos(self, evidencias, mapa: GrafoCiudad) -> None:
        """Noticia nueva: salen a caminar los testigos de sus evidencias de tipo TESTIGO (y se van los anteriores)."""
        self.transeuntes = [t for t in self.transeuntes if t.testigo is None]
        geo = geometria()
        for e in evidencias:
            if e.lugar in mapa:
                self.transeuntes.append(Transeunte(f"testigo:{e.id}", e.titulo, "CITIZEN", e.lugar,
                                                   list(geo.centros[e.lugar]), testigo=e.id))

    def poner_personajes(self, personajes, ciudadanos: dict, mapa: GrafoCiudad) -> None:
        """Dia nuevo: solo los personajes de la historia hablan (ademas de los testigos de la noticia, que puso
        `poner_testigos`); quien tiene algo que decir sale a caminar (si no estaba ya) desde su zona."""
        for t in self.transeuntes:
            t.dice = None
        geo = geometria()
        for i, dice in personajes:
            if i.startswith("testigo:") or not dice:
                continue
            t = self.buscar(i)
            c = ciudadanos.get(i)
            if t is None and c is not None and c.zona in mapa:
                t = Transeunte(c.id, c.nombre, c.rol.name, c.zona, list(geo.centros[c.zona]))
                self.transeuntes.append(t)
            if t is not None:
                t.dice = dice

    def buscar(self, id: str) -> Transeunte | None:
        return next((t for t in self.transeuntes if t.id == id), None)

    def cerca(self, pos: tuple[float, float], sirve=lambda t: True, radio: float | None = None) -> Transeunte | None:
        """El mas cercano a `pos` dentro del radio para hablar, de los que interesan (rumor o testigo) y `sirve`."""
        radio = datos()["radio"] if radio is None else radio
        d, t = min(((math.dist(pos, t.pos), t) for t in self.transeuntes if t.interesa and sirve(t)),
                   key=lambda x: x[0], default=(math.inf, None))
        return t if d <= radio else None

    def amanecer(self) -> None:
        """Dia nuevo: nadie sigue enojado."""
        for t in self.transeuntes:
            t.regado, t.enojado = False, 0.0

    def actualizar(self, dt: float, mapa: GrafoCiudad) -> list[Transeunte]:
        """Mueve a todos. Devuelve los que acaban de llegar a su destino."""
        llegados = []
        for t in self.transeuntes:
            t.enojado = max(0.0, t.enojado - dt)
            if t.zona not in mapa:   # su zona dejo de existir (no deberia): vuelve al centro de la Plaza
                t.zona, t.zonas, t.puntos = mapa.zona_inicial, [], []
            if any(a not in mapa or b not in mapa or mapa.distancia(a, b) is None for a, b in zip(t.zonas, t.zonas[1:])):
                self._rumbo(t, mapa)   # una protesta cerro una frontera de su ruta: recalcula desde donde esta
            if t.espera > 0:
                t.espera -= dt
                if t.espera <= 0:
                    self._rumbo(t, mapa)
                continue
            if not t.puntos:
                self._rumbo(t, mapa)
                continue
            if self._caminar(t, dt):
                t.espera = datos()["espera"]
                llegados.append(t)
        return llegados

    def _rumbo(self, t: Transeunte, mapa: GrafoCiudad) -> None:
        """Destino al azar entre las zonas alcanzables (BFS) y el camino mas corto a pie (Dijkstra)."""
        alcanzables = sorted(z for z in mapa.saltos(t.zona) if z != t.zona)
        if not alcanzables:          # aislada: se queda donde esta y vuelve a intentar despues
            t.zonas, t.puntos, t.espera = [t.zona], [], datos()["espera"]
            return
        zonas, puntos = rutas.ruta_puntos(mapa, geometria(), t.zona, self.rng.choice(alcanzables))
        t.zonas, t.puntos, t.espera = list(zonas), [list(p) for p in puntos], 0.0

    def _caminar(self, t: Transeunte, dt: float) -> bool:
        """Avanza en linea recta hacia el siguiente punto. True si llego al ultimo."""
        paso = datos()["velocidad"] * dt
        while t.puntos and paso > 0:
            objetivo = t.puntos[0]
            d = math.dist(t.pos, objetivo)
            if d > paso:
                f = paso / d
                t.pos = [t.pos[0] + (objetivo[0] - t.pos[0]) * f, t.pos[1] + (objetivo[1] - t.pos[1]) * f]
                return False
            t.pos, paso = list(objetivo), paso - d
            t.puntos.pop(0)
            if len(t.zonas) > 1 and tuple(objetivo) == geometria().paso(t.zonas[0], t.zonas[1]):
                t.zonas.pop(0)       # cruzo la frontera: ya esta en la otra zona
                t.zona = t.zonas[0]
        return not t.puntos

    def to_dict(self) -> dict:
        s = self.rng.getstate()
        return {"transeuntes": [asdict(t) for t in self.transeuntes], "rng": [s[0], list(s[1]), s[2]]}

    @classmethod
    def from_dict(cls, d: dict) -> "Calle":
        calle = cls([Transeunte(**t) for t in d["transeuntes"]], 0)
        calle.rng.setstate((d["rng"][0], tuple(d["rng"][1]), d["rng"][2]))
        return calle
