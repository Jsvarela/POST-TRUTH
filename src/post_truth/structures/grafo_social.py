"""Grafo social de Ciudad Nova: lista de adyacencia dirigida y ponderada. Logica pura (sin pygame).

PROBLEMA QUE RESUELVE
    Cuando el jugador comparte una publicacion hay que saber quien la recibe, cuantas
    personas, que tan rapido y que consecuencias deja. Eso es alcanzabilidad sobre una
    red de relaciones con pesos: un grafo.

REPRESENTACION (por que lista de adyacencia)
    Vertices = ciudadanos con rol. Arista dirigida u -> v = "lo que u publica le llega a v"
    (v es su amigo, confia en u o lo sigue). El peso en (0, 1] es la probabilidad base de
    que v lo reciba y, a la vez, la velocidad: mas peso = mas rapido.
    Se guarda como dict[origen] -> dict[destino] -> Arista. Es una lista de adyacencia
    (cada vertice conoce solo sus vecinos) y espacio O(V + E); usar un dict por vertice
    en vez de una lista permite consultar o borrar una arista en O(1) en lugar de O(grado).
    El grafo es disperso (cada persona conoce a pocas), asi que una matriz de adyacencia
    gastaria O(V^2) sin necesidad.

ALGORITMOS (ver `propagar`)
    * BFS por olas: da QUIEN la recibe en cada ola, CUANTOS y alimenta la animacion. O(V + E).
    * Dijkstra (heapq): da QUE TAN RAPIDO. BFS cuenta saltos, pero no distingue una arista
      de peso 0.9 (rapida) de una de 0.2 (lenta); con costo 1/peso el camino mas corto es el
      mas rapido. O(E log V). Se justifica porque el tiempo de llegada es una suma de pesos,
      que es justo el caso para el que BFS no sirve.
"""
from __future__ import annotations

import heapq
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from post_truth.models import Impact, Role

# Piso del peso: un peso 0 equivaldria a no tener relacion (para eso esta eliminar_arista)
# y haria infinito el costo 1/peso del Dijkstra.
PESO_MIN = 0.02

# Cuanto cambia el rol de quien comparte la probabilidad de contagio de sus aristas.
# El Influencer reutiliza el 1.35 de Impact.scaled_for_role para que ambos modelos coincidan.
FACTOR_EMISOR: dict[Role, float] = {
    Role.CITIZEN: 1.0, Role.JOURNALIST: 1.0, Role.INFLUENCER: 1.35, Role.CANDIDATE: 1.1,
}
FACTOR_PERIODISTA_VERDADERA = 1.2  # un periodista difunde mas lo que ya esta verificado


class TipoRelacion(Enum):
    AMISTAD = "amistad"
    CONFIANZA = "confianza"
    SEGUIMIENTO = "seguimiento"


@dataclass
class Ciudadano:
    id: str
    nombre: str
    rol: Role
    pos: tuple[float, float] = (0.5, 0.5)  # 0..1, solo para que la vista sepa donde dibujar

    def to_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "rol": self.rol.name, "pos": list(self.pos)}

    @classmethod
    def from_dict(cls, d: dict) -> "Ciudadano":
        x, y = d.get("pos", (0.5, 0.5))
        return cls(d["id"], d["nombre"], Role[d["rol"]], (float(x), float(y)))


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
    """Que paso al propagar una publicacion. Es un dato inmutable: la vista lo anima."""
    origen: str
    es_falsa: bool
    olas: tuple[tuple[str, ...], ...]        # olas[0] = (origen,); olas[k] = quienes la reciben en la ola k
    padres: dict[str, str]                   # arista del arbol BFS: quien le paso la noticia a quien
    frenados: tuple[str, ...]                # la recibieron pero no la retransmiten (periodista ante una falsa)
    tiempos: dict[str, float]                # Dijkstra: tiempo minimo de llegada por ciudadano (horas simuladas)
    poblacion: int                           # ciudadanos posibles receptores (sin contar al origen)

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
        """Tiempo hasta que la recibe la mitad de los alcanzados (mas estable que el maximo)."""
        llegadas = sorted(t for c, t in self.tiempos.items() if c != self.origen)
        return llegadas[(len(llegadas) - 1) // 2] if llegadas else 0.0

    @property
    def rapidez(self) -> float:
        """Personas por hora simulada."""
        return self.alcanzados / self.tiempo_total if self.tiempo_total > 0 else 0.0

    def impacto(self) -> Impact:
        """Consecuencia en la ciudad segun la veracidad y el alcance. Falsa: sube la
        desinformacion y los conflictos y baja la confianza; verdadera: sube la informacion
        verificada y la confianza. Cada efecto tiene tope para que una sola publicacion no
        decida la partida."""
        n = self.alcanzados
        if n == 0:
            return Impact()
        if self.es_falsa:
            return Impact(misinformation=min(12, round(1.5 * n)), conflicts=min(8, round(0.8 * n)),
                          trust=-min(8, round(0.7 * n)), score=-min(10, n))
        return Impact(verified_information=min(10, round(1.2 * n)), trust=min(6, round(0.5 * n)),
                      coexistence=min(4, round(0.3 * n)), score=min(10, n))

    def to_dict(self) -> dict:
        return {"origen": self.origen, "es_falsa": self.es_falsa,
                "olas": [list(o) for o in self.olas], "padres": dict(self.padres),
                "frenados": list(self.frenados), "tiempos": dict(self.tiempos),
                "poblacion": self.poblacion}


@dataclass
class GrafoSocial:
    _vertices: dict[str, Ciudadano] = field(default_factory=dict)
    _ady: dict[str, dict[str, Arista]] = field(default_factory=dict)

    # --- vertices -----------------------------------------------------------------------
    def agregar_vertice(self, ciudadano: Ciudadano) -> None:
        """O(1)."""
        if ciudadano.id in self._vertices:
            raise ValueError(f"Ya existe el ciudadano: {ciudadano.id}")
        self._vertices[ciudadano.id] = ciudadano
        self._ady[ciudadano.id] = {}

    def eliminar_vertice(self, id: str) -> None:
        """Quita el vertice y TODAS sus aristas, salientes y entrantes. Las salientes se van con
        su diccionario (O(1)); las entrantes viven en los diccionarios de los demas vertices, asi
        que se hace un pop O(1) en cada uno: O(V) en total."""
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

    # --- aristas ------------------------------------------------------------------------
    def agregar_arista(self, origen: str, destino: str, peso: float,
                       tipo: TipoRelacion = TipoRelacion.AMISTAD) -> Arista:
        """O(1). Dirigida: origen -> destino no implica destino -> origen."""
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
        """O(1). Devuelve False si no existia."""
        self._exigir(origen)
        return self._ady[origen].pop(destino, None) is not None

    def arista(self, origen: str, destino: str) -> Arista | None:
        self._exigir(origen)
        return self._ady[origen].get(destino)

    def vecinos(self, id: str) -> list[Arista]:
        """Aristas salientes de `id` (a quienes les llega lo que publica). O(grado)."""
        self._exigir(id)
        return list(self._ady[id].values())

    def aristas(self) -> list[Arista]:
        return [a for vecinos in self._ady.values() for a in vecinos.values()]

    # --- intervenciones del jugador (Verificar / Reportar) --------------------------------
    def debilitar_salientes(self, id: str, factor: float) -> list[tuple[str, str]]:
        """Multiplica por `factor` (0..1) el peso de las aristas salientes: la noticia sigue
        circulando pero mas lento y con menos alcance (efecto de Verificar). O(grado)."""
        if not 0 < factor <= 1:
            raise ValueError("factor debe estar en (0, 1]")
        for a in self.vecinos(id):
            a.peso = max(PESO_MIN, a.peso * factor)
        return [(a.origen, a.destino) for a in self.vecinos(id)]

    def cortar_salientes(self, id: str) -> list[tuple[str, str]]:
        """Elimina todas las aristas salientes: la cuenta deja de difundir (efecto de Reportar). O(grado)."""
        cortadas = [(a.origen, a.destino) for a in self.vecinos(id)]
        self._ady[id].clear()
        return cortadas

    # --- propagacion --------------------------------------------------------------------
    def propagar(self, origen: str, es_falsa: bool,
                 rng: random.Random | None = None) -> ResultadoPropagacion:
        """Simula como se difunde una publicacion que parte de `origen`.

        Modelo (cascada independiente): cuando un ciudadano ya contagiado es procesado, cada
        arista saliente "se activa" una sola vez con probabilidad min(1, peso * factor_rol).
        Para tener en cuenta el rol: el Influencer amplifica (x1.35); el Periodista no
        retransmite una noticia falsa (la desmiente) y difunde mas una verdadera.

        1) BFS por olas: la cola es la ola actual; sus vecinos nuevos forman la siguiente.
           Cada arista se evalua una sola vez => O(V + E). Se eligio BFS porque la
           pregunta es "quien recibe en cada ola" (nivel = ola) y eso es exactamente un BFS.
        2) Dijkstra sobre las aristas que SI se activaron (costo 1/peso) => tiempo minimo de
           llegada de cada ciudadano. No se usa BFS para el tiempo porque la ola solo cuenta
           saltos, y un camino de 3 saltos fuertes puede ser mas rapido que uno de 2 debiles.
           O(E log V) con cola de prioridad binaria.
        """
        self._exigir(origen)
        rng = rng or random.Random()
        visitados = {origen}
        olas: list[tuple[str, ...]] = [(origen,)]
        padres: dict[str, str] = {}
        frenados: list[str] = []
        activas: dict[str, list[tuple[str, float]]] = {}  # aristas activadas: u -> [(v, costo)]

        frontera = [origen]
        while frontera:
            siguiente: list[str] = []
            for u in frontera:
                emisor = self._vertices[u]
                if es_falsa and emisor.rol is Role.JOURNALIST and u != origen:
                    frenados.append(u)  # lee la noticia pero la verifica en vez de reenviarla
                    continue
                factor = FACTOR_EMISOR[emisor.rol]
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

    # --- serializacion (para el servidor de sockets) ------------------------------------
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
            continue  # entrada vieja: ya se encontro un camino mejor
        for v, costo in activas.get(u, ()):
            nd = d + costo
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(cola, (nd, v))
    return dist
