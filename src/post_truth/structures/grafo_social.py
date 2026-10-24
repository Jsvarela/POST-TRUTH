"""Grafo social de Ciudad Nova: lista de adyacencia dirigida y ponderada."""
from __future__ import annotations

import heapq
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from post_truth.models import Impact, Role

PESO_MIN = 0.02

PROPAGACION_FALSA = {"desinformacion": (3.5, 24), "conflictos": (0.8, 8), "confianza": (0.7, 8), "puntaje": (1.0, 10)}
PROPAGACION_VERDADERA = {"verificada": (1.2, 10), "confianza": (0.5, 6), "convivencia": (0.3, 4), "puntaje": (1.0, 10)}

FACTOR_EMISOR: dict[Role, float] = {
    Role.CITIZEN: 1.0, Role.JOURNALIST: 1.0, Role.INFLUENCER: 1.35, Role.CANDIDATE: 1.1,
}
FACTOR_PERIODISTA_VERDADERA = 1.2


class TipoRelacion(Enum):
    AMISTAD = "amistad"
    CONFIANZA = "confianza"
    SEGUIMIENTO = "seguimiento"


@dataclass
class Ciudadano:
    id: str
    nombre: str
    rol: Role
    pos: tuple[float, float] = (0.5, 0.5)
    zona: str | None = None   # zona de la ciudad donde vive (R9: si queda aislada, no le llegan desmentidos)

    def to_dict(self) -> dict:
        d = {"id": self.id, "nombre": self.nombre, "rol": self.rol.name, "pos": list(self.pos)}
        return d | ({"zona": self.zona} if self.zona else {})

    @classmethod
    def from_dict(cls, d: dict) -> "Ciudadano":
        x, y = d.get("pos", (0.5, 0.5))
        return cls(d["id"], d["nombre"], Role[d["rol"]], (float(x), float(y)), d.get("zona"))


@dataclass
class Arista:
    origen: str
    destino: str
    peso: float
    tipo: TipoRelacion = TipoRelacion.AMISTAD

    def to_dict(self) -> dict:
        return {"origen": self.origen, "destino": self.destino, "peso": round(self.peso, 4),
                "tipo": self.tipo.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Arista":
        return cls(d["origen"], d["destino"], float(d["peso"]), TipoRelacion(d.get("tipo", "amistad")))


@dataclass(frozen=True)
class ResultadoPropagacion:
    """Que paso al propagar una publicacion."""
    origen: str
    es_falsa: bool
    olas: tuple[tuple[str, ...], ...]
    padres: dict[str, str]
    frenados: tuple[str, ...]
    tiempos: dict[str, float]
    poblacion: int

    @property
    def alcanzados(self) -> int:
        return sum(len(ola) for ola in self.olas[1:])

    @property
    def n_olas(self) -> int:
        return len(self.olas) - 1

    @property
    def tiempo_total(self) -> float:
        llegadas = [t for c, t in self.tiempos.items() if c != self.origen]
        return max(llegadas, default=0.0)

    @property
    def tiempo_mitad(self) -> float:
        """Tiempo hasta que la recibe la mitad de los alcanzados."""
        llegadas = sorted(t for c, t in self.tiempos.items() if c != self.origen)
        return llegadas[(len(llegadas) - 1) // 2] if llegadas else 0.0

    @property
    def rapidez(self) -> float:
        """Personas por hora simulada."""
        return self.alcanzados / self.tiempo_total if self.tiempo_total > 0 else 0.0

    def impacto(self) -> Impact:
        """Consecuencia en la ciudad segun la veracidad y el alcance."""
        n = self.alcanzados
        if n == 0:
            return Impact()
        def efecto(tabla: dict, clave: str) -> int:
            coeficiente, tope = tabla[clave]
            return min(tope, round(coeficiente * n))
        if self.es_falsa:
            f = PROPAGACION_FALSA
            return Impact(misinformation=efecto(f, "desinformacion"), conflicts=efecto(f, "conflictos"),
                          trust=-efecto(f, "confianza"), score=-efecto(f, "puntaje"))
        v = PROPAGACION_VERDADERA
        return Impact(verified_information=efecto(v, "verificada"), trust=efecto(v, "confianza"),
                      coexistence=efecto(v, "convivencia"), score=efecto(v, "puntaje"))

    def to_dict(self) -> dict:
        return {"origen": self.origen, "es_falsa": self.es_falsa,
                "olas": [list(o) for o in self.olas], "padres": dict(self.padres),
                "frenados": list(self.frenados), "tiempos": dict(self.tiempos),
                "poblacion": self.poblacion}


@dataclass
class GrafoSocial:
    _vertices: dict[str, Ciudadano] = field(default_factory=dict)
    _ady: dict[str, dict[str, Arista]] = field(default_factory=dict)

    def agregar_vertice(self, ciudadano: Ciudadano) -> None:
        """O(1)."""
        if ciudadano.id in self._vertices:
            raise ValueError(f"Ya existe el ciudadano: {ciudadano.id}")
        self._vertices[ciudadano.id] = ciudadano
        self._ady[ciudadano.id] = {}

    def eliminar_vertice(self, id: str) -> None:
        """Quita el vertice y todas sus aristas, salientes y entrantes."""
        self._exigir(id)
        del self._vertices[id]
        del self._ady[id]
        for vecinos in self._ady.values():
            vecinos.pop(id, None)

    def vertice(self, id: str) -> Ciudadano:
        self._exigir(id)
        return self._vertices[id]

    def vertices(self) -> list[Ciudadano]:
        return list(self._vertices.values())

    def cambiar_rol(self, id: str, rol: Role) -> None:
        self.vertice(id).rol = rol

    def agregar_arista(self, origen: str, destino: str, peso: float,
                       tipo: TipoRelacion = TipoRelacion.AMISTAD) -> Arista:
        """O(1)."""
        self._exigir(origen)
        self._exigir(destino)
        if origen == destino:
            raise ValueError("Un ciudadano no puede ser su propio vecino")
        if not PESO_MIN <= peso <= 1.0:
            raise ValueError(f"El peso debe estar en [{PESO_MIN}, 1.0]: {peso}")
        if destino in self._ady[origen]:
            raise ValueError(f"Ya existe la arista {origen} -> {destino}")
        arista = Arista(origen, destino, peso, tipo)
        self._ady[origen][destino] = arista
        return arista

    def eliminar_arista(self, origen: str, destino: str) -> bool:
        """O(1)."""
        self._exigir(origen)
        return self._ady[origen].pop(destino, None) is not None

    def arista(self, origen: str, destino: str) -> Arista | None:
        self._exigir(origen)
        return self._ady[origen].get(destino)

    def vecinos(self, id: str) -> list[Arista]:
        """Aristas salientes de `id`."""
        self._exigir(id)
        return list(self._ady[id].values())

    def aristas(self) -> list[Arista]:
        return [a for vecinos in self._ady.values() for a in vecinos.values()]

    def debilitar_salientes(self, id: str, factor: float) -> list[tuple[str, str]]:
        """Multiplica por `factor` el peso de las aristas salientes."""
        if not 0 < factor <= 1:
            raise ValueError("factor debe estar en (0, 1]")
        for a in self.vecinos(id):
            a.peso = max(PESO_MIN, a.peso * factor)
        return [(a.origen, a.destino) for a in self.vecinos(id)]

    def cortar_salientes(self, id: str) -> list[tuple[str, str]]:
        """Elimina todas las aristas salientes: la cuenta deja de difundir."""
        cortadas = [(a.origen, a.destino) for a in self.vecinos(id)]
        self._ady[id].clear()
        return cortadas

    def propagar(self, origen: str, es_falsa: bool, rng: random.Random | None = None,
                 alcance_origen: float = 1.0) -> ResultadoPropagacion:
        """Simula como se difunde una publicacion que parte de `origen`."""
        self._exigir(origen)
        rng = rng or random.Random()
        visitados = {origen}
        olas: list[tuple[str, ...]] = [(origen,)]
        padres: dict[str, str] = {}
        frenados: list[str] = []
        activas: dict[str, list[tuple[str, float]]] = {}

        frontera = [origen]
        while frontera:
            siguiente: list[str] = []
            for u in frontera:
                emisor = self._vertices[u]
                if es_falsa and emisor.rol is Role.JOURNALIST and u != origen:
                    frenados.append(u)
                    continue
                factor = FACTOR_EMISOR[emisor.rol] * (alcance_origen if u == origen else 1.0)
                if not es_falsa and emisor.rol is Role.JOURNALIST:
                    factor *= FACTOR_PERIODISTA_VERDADERA
                for a in self._ady[u].values():
                    if rng.random() < min(1.0, a.peso * factor):
                        activas.setdefault(u, []).append((a.destino, 1.0 / a.peso))
                        if a.destino not in visitados:
                            visitados.add(a.destino)
                            padres[a.destino] = u
                            siguiente.append(a.destino)
            if siguiente:
                olas.append(tuple(siguiente))
            frontera = siguiente

        return ResultadoPropagacion(
            origen=origen, es_falsa=es_falsa, olas=tuple(olas), padres=padres,
            frenados=tuple(frenados), tiempos=_dijkstra(origen, activas),
            poblacion=len(self._vertices) - 1)

    def to_dict(self) -> dict:
        return {"ciudadanos": [c.to_dict() for c in self._vertices.values()],
                "relaciones": [a.to_dict() for a in self.aristas()]}

    @classmethod
    def from_dict(cls, datos: dict) -> "GrafoSocial":
        g = cls()
        for c in datos["ciudadanos"]:
            g.agregar_vertice(Ciudadano.from_dict(c))
        for r in datos["relaciones"]:
            a = Arista.from_dict(r)
            g.agregar_arista(a.origen, a.destino, a.peso, a.tipo)
        return g

    @classmethod
    def cargar(cls, ruta: str | Path) -> "GrafoSocial":
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            return cls.from_dict(json.load(archivo))

    def _exigir(self, id: str) -> None:
        if id not in self._vertices:
            raise KeyError(f"No existe el ciudadano: {id}")


def _dijkstra(origen: str, activas: dict[str, list[tuple[str, float]]]) -> dict[str, float]:
    """Tiempo minimo de llegada desde `origen` sobre las aristas activadas."""
    dist = {origen: 0.0}
    cola = [(0.0, origen)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist.get(u, float("inf")):
            continue
        for v, costo in activas.get(u, ()):
            nd = d + costo
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(cola, (nd, v))
    return dist
