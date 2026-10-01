"""Grafo de la ciudad: zonas conectadas por vias fisicas. Logica pura (sin pygame).

PROBLEMA QUE RESUELVE
    El grafo social dice COMO circula una noticia en linea; este dice DONDE ocurre y por
    donde se contagia en persona. Con el se decide a donde puede ir el jugador, que zonas
    quedan expuestas a un rumor y cuanto tarda un rumor en llegar a cada una.

REPRESENTACION
    Vertices = zonas (Colegio, Barrio, Parque, Plaza, Alcaldia). Aristas NO dirigidas y sin
    peso: una calle se recorre en los dos sentidos y todas las conexiones cuestan un
    "movimiento". Lista de adyacencia (dict zona -> lista de vecinos), espacio O(V + E): con
    solo 5 a 10 zonas y grado pequeno, buscar en la lista de vecinos es practicamente O(1)
    y mantiene el orden de insercion, de modo que los recorridos son deterministas.

ALGORITMOS
    * BFS: como las aristas no tienen peso, el camino con menos saltos es el mas corto y BFS lo
      encuentra por niveles en O(V + E). Dijkstra no aporta nada aqui (haria falta pesos).
    * Anillos de exposicion: el mismo BFS agrupado por distancia. El anillo k son las zonas a
      k saltos del origen: justo lo que un rumor alcanza tras k rondas.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Zona:
    id: str
    nombre: str
    pos: tuple[float, float] = (0.5, 0.5)  # 0..1, solo para que la vista sepa donde dibujar

    def to_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "pos": list(self.pos)}

    @classmethod
    def from_dict(cls, d: dict) -> "Zona":
        x, y = d.get("pos", (0.5, 0.5))
        return cls(d["id"], d["nombre"], (float(x), float(y)))


@dataclass
class GrafoCiudad:
    _zonas: dict[str, Zona] = field(default_factory=dict)
    _ady: dict[str, list[str]] = field(default_factory=dict)
    zona_inicial: str = ""  # donde empieza el jugador (dato de la ciudad, no del jugador)

    # --- zonas --------------------------------------------------------------------------
    def agregar_zona(self, zona: Zona) -> None:
        """O(1)."""
        if zona.id in self._zonas:
            raise ValueError(f"Ya existe la zona: {zona.id}")
        self._zonas[zona.id] = zona
        self._ady[zona.id] = []

    def eliminar_zona(self, id: str) -> None:
        """Quita la zona y todas sus conexiones: hay que borrar su id de la lista de cada vecino
        (list.remove es O(grado)), o sea O(suma de los grados de sus vecinos), a lo sumo O(E)."""
        self._exigir(id)
        for vecino in self._ady[id]:
            self._ady[vecino].remove(id)
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

    # --- conexiones ---------------------------------------------------------------------
    def agregar_conexion(self, a: str, b: str) -> None:
        """Conexion fisica (no dirigida): se anota en la lista de ambas zonas. O(grado)."""
        self._exigir(a)
        self._exigir(b)
        if a == b:
            raise ValueError("Una zona no se conecta consigo misma")
        if b in self._ady[a]:
            raise ValueError(f"Ya existe la conexion {a} - {b}")
        self._ady[a].append(b)
        self._ady[b].append(a)

    def eliminar_conexion(self, a: str, b: str) -> bool:
        """Devuelve False si no existia. O(grado)."""
        self._exigir(a)
        self._exigir(b)
        if b not in self._ady[a]:
            return False
        self._ady[a].remove(b)
        self._ady[b].remove(a)
        return True

    def vecinos(self, id: str) -> list[str]:
        """Zonas conectadas directamente a `id`, en orden de insercion. O(grado)."""
        self._exigir(id)
        return list(self._ady[id])

    def conexiones(self) -> list[tuple[str, str]]:
        """Cada conexion una sola vez (a, b)."""
        vistas: set[frozenset[str]] = set()
        resultado: list[tuple[str, str]] = []
        for a, vecinos in self._ady.items():
            for b in vecinos:
                par = frozenset((a, b))
                if par not in vistas:
                    vistas.add(par)
                    resultado.append((a, b))
        return resultado

    # --- consultas (BFS) ----------------------------------------------------------------
    def camino(self, origen: str, destino: str) -> list[str] | None:
        """Camino con menos saltos de `origen` a `destino` (ambos incluidos), o None si no
        hay ruta. BFS guardando de quien viene cada zona: O(V + E)."""
        self._exigir(origen)
        self._exigir(destino)
        padres: dict[str, str | None] = {origen: None}
        cola = deque([origen])
        while cola:
            u = cola.popleft()
            if u == destino:
                break
            for v in self._ady[u]:
                if v not in padres:
                    padres[v] = u
                    cola.append(v)
        if destino not in padres:
            return None
        ruta = [destino]
        while padres[ruta[-1]] is not None:
            ruta.append(padres[ruta[-1]])  # type: ignore[arg-type]
        return ruta[::-1]

    def distancias(self, origen: str, limite: int | None = None) -> dict[str, int]:
        """Saltos minimos desde `origen` a cada zona alcanzable (BFS por niveles). Con `limite`
        el recorrido se corta en esa profundidad. O(V + E)."""
        self._exigir(origen)
        dist = {origen: 0}
        cola = deque([origen])
        while cola:
            u = cola.popleft()
            if limite is not None and dist[u] >= limite:
                continue
            for v in self._ady[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    cola.append(v)
        return dist

    def expuestas(self, origen: str, alcance: int) -> list[tuple[str, ...]]:
        """Zonas expuestas a un rumor que nace en `origen`, por anillos: el elemento i-1 son las
        zonas a i saltos (i = 1..alcance), o sea las que el rumor toca en la ronda i. Los anillos
        vacios se omiten al final. Es el BFS de `distancias` agrupado por nivel: O(V + E)."""
        dist = self.distancias(origen, alcance)
        anillos: list[list[str]] = [[] for _ in range(alcance)]
        for zona, d in dist.items():
            if d > 0:
                anillos[d - 1].append(zona)
        while anillos and not anillos[-1]:
            anillos.pop()
        return [tuple(a) for a in anillos]

    # --- serializacion (para el servidor de sockets) ------------------------------------
    def to_dict(self) -> dict:
        return {"zonas": [z.to_dict() for z in self._zonas.values()],
                "conexiones": [list(c) for c in self.conexiones()],
                "zona_inicial": self.zona_inicial}

    @classmethod
    def from_dict(cls, datos: dict) -> "GrafoCiudad":
        g = cls()
        for z in datos["zonas"]:
            g.agregar_zona(Zona.from_dict(z))
        for a, b in datos["conexiones"]:
            g.agregar_conexion(a, b)
        g.zona_inicial = datos.get("zona_inicial", "")
        if g.zona_inicial and g.zona_inicial not in g:
            raise ValueError(f"zona_inicial desconocida: {g.zona_inicial}")
        return g

    @classmethod
    def cargar(cls, ruta: str | Path) -> "GrafoCiudad":
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            return cls.from_dict(json.load(archivo))

    def _exigir(self, id: str) -> None:
        if id not in self._zonas:
            raise KeyError(f"No existe la zona: {id}")
