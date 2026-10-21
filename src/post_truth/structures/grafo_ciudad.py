"""Grafo de la ciudad: lugares conectados por vias con distancia."""
from __future__ import annotations

import heapq
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Ruta:
    """Camino de `zonas[0]` a `zonas[-1]` y su distancia total."""
    zonas: tuple[str, ...]
    costo: int

    @property
    def tramos(self) -> list[tuple[str, str]]:
        """Pares consecutivos del camino: las aristas que se recorren."""
        return list(zip(self.zonas, self.zonas[1:]))


@dataclass
class Zona:
    id: str
    nombre: str
    pos: tuple[float, float] = (0.5, 0.5)

    def to_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "pos": list(self.pos)}

    @classmethod
    def from_dict(cls, d: dict) -> "Zona":
        x, y = d.get("pos", (0.5, 0.5))
        return cls(d["id"], d["nombre"], (float(x), float(y)))


@dataclass
class GrafoCiudad:
    _zonas: dict[str, Zona] = field(default_factory=dict)
    _ady: dict[str, dict[str, int]] = field(default_factory=dict)
    zona_inicial: str = ""

    def agregar_zona(self, zona: Zona) -> None:
        """O(1)."""
        if zona.id in self._zonas:
            raise ValueError(f"Ya existe la zona: {zona.id}")
        self._zonas[zona.id] = zona
        self._ady[zona.id] = {}

    def eliminar_zona(self, id: str) -> None:
        """Quita la zona y todas sus conexiones."""
        self._exigir(id)
        for vecino in self._ady[id]:
            del self._ady[vecino][id]
        del self._ady[id]
        del self._zonas[id]
        if self.zona_inicial == id:
            self.zona_inicial = ""

    def zona(self, id: str) -> Zona:
        self._exigir(id)
        return self._zonas[id]

    def zonas(self) -> list[Zona]:
        return list(self._zonas.values())

    def __contains__(self, id: str) -> bool:
        return id in self._zonas

    def agregar_conexion(self, a: str, b: str, distancia: int = 1) -> None:
        """Conexion fisica de `distancia` >= 1: se anota en las dos zonas."""
        self._exigir(a)
        self._exigir(b)
        if a == b:
            raise ValueError("Una zona no se conecta consigo misma")
        if isinstance(distancia, bool) or not isinstance(distancia, int) or distancia < 1:
            raise ValueError(f"La distancia debe ser un entero >= 1: {distancia!r}")
        if b in self._ady[a]:
            raise ValueError(f"Ya existe la conexion {a} - {b}")
        self._ady[a][b] = distancia
        self._ady[b][a] = distancia

    def eliminar_conexion(self, a: str, b: str) -> bool:
        """Devuelve False si no existia."""
        self._exigir(a)
        self._exigir(b)
        if b not in self._ady[a]:
            return False
        del self._ady[a][b]
        del self._ady[b][a]
        return True

    def distancia(self, a: str, b: str) -> int | None:
        """Distancia de la via directa a - b, o None si no estan conectadas."""
        self._exigir(a)
        self._exigir(b)
        return self._ady[a].get(b)

    def vecinos(self, id: str) -> list[str]:
        """Zonas conectadas directamente a `id`, en orden de insercion."""
        self._exigir(id)
        return list(self._ady[id])

    def conexiones(self) -> list[tuple[str, str, int]]:
        """Cada conexion una sola vez:."""
        vistas: set[frozenset[str]] = set()
        resultado: list[tuple[str, str, int]] = []
        for a, vecinos in self._ady.items():
            for b, d in vecinos.items():
                par = frozenset((a, b))
                if par not in vistas:
                    vistas.add(par)
                    resultado.append((a, b, d))
        return resultado

    def costos_desde(self, origen: str) -> dict[str, int]:
        """Costo del camino mas corto de `origen` a cada zona alcanzable."""
        return self._dijkstra(origen)[0]

    def ruta(self, origen: str, destino: str) -> Ruta | None:
        """Camino de menor costo de `origen` a `destino`, o None si no hay ruta."""
        self._exigir(destino)
        costos, padres = self._dijkstra(origen, destino)
        if destino not in costos:
            return None
        camino = [destino]
        while padres[camino[-1]] is not None:
            camino.append(padres[camino[-1]])
        return Ruta(tuple(reversed(camino)), costos[destino])

    def _dijkstra(self, origen: str, destino: str | None = None) -> tuple[dict[str, int], dict[str, str | None]]:
        self._exigir(origen)
        costos: dict[str, int] = {origen: 0}
        padres: dict[str, str | None] = {origen: None}
        cola: list[tuple[int, str]] = [(0, origen)]
        hechas: set[str] = set()
        while cola:
            costo, u = heapq.heappop(cola)
            if u in hechas:
                continue
            hechas.add(u)
            if u == destino:
                break
            for v, d in self._ady[u].items():
                nuevo = costo + d
                if nuevo < costos.get(v, float("inf")):
                    costos[v] = nuevo
                    padres[v] = u
                    heapq.heappush(cola, (nuevo, v))
        return costos, padres

    def saltos(self, origen: str) -> dict[str, int]:
        """Numero minimo de saltos de `origen` a cada zona alcanzable (BFS, O(V + E))."""
        self._exigir(origen)
        dist = {origen: 0}
        cola = deque([origen])
        while cola:
            u = cola.popleft()
            for v in self._ady[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    cola.append(v)
        return dist

    def es_conexo(self) -> bool:
        """True si desde cualquier zona se puede llegar a todas las demas."""
        if not self._zonas:
            return True
        return len(self.saltos(next(iter(self._zonas)))) == len(self._zonas)

    def to_dict(self) -> dict:
        return {"zonas": [z.to_dict() for z in self._zonas.values()],
                "conexiones": [{"origen": a, "destino": b, "distancia": d} for a, b, d in self.conexiones()],
                "zona_inicial": self.zona_inicial}

    @classmethod
    def from_dict(cls, datos: dict) -> "GrafoCiudad":
        g = cls()
        for z in datos["zonas"]:
            g.agregar_zona(Zona.from_dict(z))
        for c in datos["conexiones"]:
            g.agregar_conexion(c["origen"], c["destino"], c["distancia"])
        g.zona_inicial = datos.get("zona_inicial", "")
        if g.zona_inicial and g.zona_inicial not in g:
            raise ValueError(f"zona_inicial desconocida: {g.zona_inicial}")
        return g

    @classmethod
    def cargar(cls, ruta: str | Path, exigir_conexo: bool = True) -> "GrafoCiudad":
        """Carga el mapa de data/."""
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            g = cls.from_dict(json.load(archivo))
        if exigir_conexo and not g.es_conexo():
            raise ValueError("El mapa de la ciudad debe ser conexo: hay zonas inalcanzables")
        return g

    def _exigir(self, id: str) -> None:
        if id not in self._zonas:
            raise KeyError(f"No existe la zona: {id}")
