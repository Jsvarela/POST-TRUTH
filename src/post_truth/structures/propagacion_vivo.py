"""Propagacion EN VIVO de un rumor por el grafo social, con acciones del jugador. Logica pura y serializable.

RECORRIDO: BFS por olas, UNA OLA POR PASO DE TIEMPO. El "frente" (los ciudadanos activos en este paso) es el
nivel del BFS: en cada paso cada activo intenta pasar la noticia a sus vecinos que aun no la conocen, y los que la
reciben forman el frente del paso siguiente. Asi se sabe quien la recibe y CUANDO, que es lo que se anima en vivo.
- Por que BFS y no DFS: DFS recorreria una rama hasta el fondo y no da tiempos de llegada.
- Por que no Dijkstra: aqui el tiempo ya es discreto (un paso = una ola), no hace falta.
- Complejidad: un paso cuesta O(suma de grados del frente). Cada ciudadano queda activo a lo sumo ACTIVO pasos
  (constante), asi que la simulacion entera cuesta O(ACTIVO * (V + E)) = O(V + E).

Dos frentes compiten: el RUMOR (falso) y el DESMENTIDO (verdadero). Estados de cada ciudadano:
sin_enterarse -> enterado (la cree) -> compartio (la difunde); o inmune (verifico o le llego el desmentido).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from post_truth.models import Impact, Role
from post_truth.structures.grafo_social import (FACTOR_EMISOR, PROPAGACION_FALSA, PROPAGACION_VERDADERA,
                                                GrafoSocial)

SIN_ENTERARSE, ENTERADO, COMPARTIO, INMUNE = "sin_enterarse", "enterado", "compartio", "inmune"
PASO = 1.0              # segundos por paso (una ola)
ACTIVO = 10             # pasos que un ciudadano sigue difundiendo (ajustado con tools/balance.py --en-vivo)
TRANSMISION = 0.7       # escala de la probabilidad por intento
COMPARTE = {Role.CITIZEN: 0.9, Role.INFLUENCER: 1.0, Role.CANDIDATE: 0.8, Role.JOURNALIST: 0.0}
CREDIBILIDAD_ROL = {Role.CITIZEN: 50, Role.INFLUENCER: 50, Role.CANDIDATE: 60, Role.JOURNALIST: 80}
ENFRIAMIENTO = {"verificador": 8.0, "limitar": 10.0, "desmentido": 15.0, "alertar": 20.0}
FACTOR_LIMITAR = 0.4    # primera vez: sus aristas salientes conservan el 40%; segunda vez: se eliminan
ACELERA_PERIODISTAS, DURACION_ALERTA = 2.0, 10.0


@dataclass(frozen=True)
class ResultadoAccion:
    ok: bool
    motivo: str = ""     # "" | enfriando | ciudadano_desconocido | ya_lanzado


class PropagacionEnVivo:
    def __init__(self, grafo: GrafoSocial, autor: str, jugador: str, credibilidad_jugador: int,
                 semilla: int = 0, es_falsa: bool = True) -> None:
        self.grafo = grafo
        self.autor, self.jugador, self.es_falsa = autor, jugador, es_falsa
        self.credibilidad_jugador = credibilidad_jugador
        self.rng = random.Random(semilla)
        self.estado = {c.id: SIN_ENTERARSE for c in grafo.vertices()}
        self.rumor: dict[str, int] = {}       # frente del rumor: id -> pasos que le quedan activo
        self.desmentido: dict[str, int] = {}  # frente del desmentido
        self.enfriando = {a: 0.0 for a in ENFRIAMIENTO}
        self.limitadas: list[str] = []
        self.alerta = 0.0                     # segundos que quedan de periodistas acelerados
        self.t, self._acumulado, self.pasos = 0.0, 0.0, 0
        self.estado[autor] = COMPARTIO
        self.rumor[autor] = ACTIVO

    # --- reloj --------------------------------------------------------------------------------
    @property
    def terminada(self) -> bool:
        return not self.rumor and not self.desmentido

    def avanzar(self, dt: float) -> None:
        """Acumula `dt` y da un paso por cada PASO segundos: igual a 30 y a 60 FPS."""
        self.t += dt
        for accion in self.enfriando:
            self.enfriando[accion] = max(0.0, self.enfriando[accion] - dt)
        self.alerta = max(0.0, self.alerta - dt)
        self._acumulado += dt
        while self._acumulado >= PASO - 1e-9 and not self.terminada:   # tolerancia: 90 x 1/30 da 2.999...
            self._acumulado -= PASO
            self.paso()

    @property
    def progreso_paso(self) -> float:
        """0..1 del paso en curso: la vista lo usa para mover la noticia por las aristas."""
        return min(1.0, self._acumulado / PASO)

    def _credibilidad(self, id: str) -> int:
        return self.credibilidad_jugador if id == self.jugador else CREDIBILIDAD_ROL[self.grafo.vertice(id).rol]

    def _probabilidad(self, emisor: str, peso: float, desmentido: bool) -> float:
        rol = self.grafo.vertice(emisor).rol
        p = peso * FACTOR_EMISOR[rol] * (0.5 + self._credibilidad(emisor) / 100) * TRANSMISION
        if desmentido and rol is Role.JOURNALIST and self.alerta > 0:
            p *= ACELERA_PERIODISTAS
        return min(1.0, p)

    def paso(self) -> None:
        """Una ola: primero el desmentido (quien lo recibe ya no cae en el rumor del mismo paso), luego el rumor."""
        self.pasos += 1
        nuevo_desmentido: dict[str, int] = {}
        for u in self.desmentido:
            for a in self.grafo.vecinos(u):
                if self.estado.get(a.destino) in (SIN_ENTERARSE, ENTERADO) \
                        and self.rng.random() < self._probabilidad(u, a.peso, True):
                    self.estado[a.destino] = INMUNE
                    nuevo_desmentido[a.destino] = ACTIVO
        nuevo_rumor: dict[str, int] = {}
        for u in self.rumor:
            for a in self.grafo.vecinos(u):
                if self.estado.get(a.destino) == SIN_ENTERARSE and self.rng.random() < self._probabilidad(u, a.peso, False):
                    self._recibir_rumor(a.destino, nuevo_rumor)
        self.desmentido = _seguir(self.desmentido, nuevo_desmentido)
        self.rumor = _seguir({u: n for u, n in self.rumor.items() if self.estado[u] == COMPARTIO}, nuevo_rumor)

    def _recibir_rumor(self, id: str, nuevo: dict[str, int]) -> None:
        rol = self.grafo.vertice(id).rol
        if self.es_falsa and rol is Role.JOURNALIST:      # un periodista verifica antes de compartir
            self.estado[id] = INMUNE
        elif self.rng.random() < COMPARTE[rol]:
            self.estado[id] = COMPARTIO
            nuevo[id] = ACTIVO
        else:
            self.estado[id] = ENTERADO

    # --- acciones del jugador --------------------------------------------------------------------
    def _puede(self, accion: str, ciudadano: str | None = None) -> ResultadoAccion:
        if self.enfriando[accion] > 0:
            return ResultadoAccion(False, "enfriando")
        if ciudadano is not None and ciudadano not in self.estado:
            return ResultadoAccion(False, "ciudadano_desconocido")
        return ResultadoAccion(True)

    def poner_verificador(self, ciudadano: str) -> ResultadoAccion:
        """El ciudadano y sus vecinos directos que no la han compartido quedan inmunes."""
        r = self._puede("verificador", ciudadano)
        if r.ok:
            for id in [ciudadano] + [a.destino for a in self.grafo.vecinos(ciudadano)]:
                if self.estado[id] != COMPARTIO:
                    self.estado[id] = INMUNE
            self.enfriando["verificador"] = ENFRIAMIENTO["verificador"]
        return r

    def limitar_cuenta(self, ciudadano: str) -> ResultadoAccion:
        """Primera vez: sus aristas salientes bajan al 40%. Sobre una cuenta ya limitada: se eliminan."""
        r = self._puede("limitar", ciudadano)
        if r.ok:
            if ciudadano in self.limitadas:
                self.grafo.cortar_salientes(ciudadano)
            else:
                self.grafo.debilitar_salientes(ciudadano, FACTOR_LIMITAR)
                self.limitadas.append(ciudadano)
            self.enfriando["limitar"] = ENFRIAMIENTO["limitar"]
        return r

    def lanzar_desmentido(self) -> ResultadoAccion:
        """Un frente verdadero que parte del jugador, con la fuerza de su credibilidad."""
        r = self._puede("desmentido")
        if r.ok:
            self.estado[self.jugador] = INMUNE
            self.desmentido[self.jugador] = ACTIVO
            self.enfriando["desmentido"] = ENFRIAMIENTO["desmentido"]
        return r

    def alertar_periodistas(self) -> ResultadoAccion:
        """Los periodistas desmienten y, por un rato, transmiten el doble de rapido."""
        r = self._puede("alertar")
        if r.ok:
            for c in self.grafo.vertices():
                if c.rol is Role.JOURNALIST and self.estado[c.id] != COMPARTIO:
                    self.estado[c.id] = INMUNE
                    self.desmentido[c.id] = ACTIVO
            self.alerta = DURACION_ALERTA
            self.enfriando["alertar"] = ENFRIAMIENTO["alertar"]
        return r

    # --- resultado ----------------------------------------------------------------------------
    def contar(self, estado: str) -> int:
        return sum(1 for e in self.estado.values() if e == estado)

    @property
    def creen(self) -> int:
        return self.contar(ENTERADO) + self.contar(COMPARTIO)

    def impacto(self) -> Impact:
        """Mismas tablas que la propagacion de siempre: la desinformacion sube con los que la creen y la
        informacion verificada con los inmunes (sin contar al jugador)."""
        def efecto(tabla: dict, clave: str, n: int) -> int:
            coeficiente, tope = tabla[clave]
            return min(tope, round(coeficiente * n))
        creen = self.creen
        inmunes = self.contar(INMUNE) - (self.estado.get(self.jugador) == INMUNE)
        f, v = PROPAGACION_FALSA, PROPAGACION_VERDADERA
        return (Impact(misinformation=efecto(f, "desinformacion", creen), conflicts=efecto(f, "conflictos", creen),
                       trust=-efecto(f, "confianza", creen), score=-efecto(f, "puntaje", creen))
                + Impact(verified_information=efecto(v, "verificada", inmunes), trust=efecto(v, "confianza", inmunes),
                         coexistence=efecto(v, "convivencia", inmunes), score=efecto(v, "puntaje", inmunes)))

    # --- serializacion ------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Todo menos el grafo, que lo guarda la sesion (las cuentas limitadas quedan en el)."""
        s = self.rng.getstate()
        return {"autor": self.autor, "jugador": self.jugador, "es_falsa": self.es_falsa,
                "credibilidad_jugador": self.credibilidad_jugador, "estado": self.estado, "rumor": self.rumor,
                "desmentido": self.desmentido, "enfriando": self.enfriando, "limitadas": self.limitadas,
                "alerta": self.alerta, "t": self.t, "acumulado": self._acumulado, "pasos": self.pasos,
                "rng": [s[0], list(s[1]), s[2]]}

    @classmethod
    def from_dict(cls, d: dict, grafo: GrafoSocial) -> "PropagacionEnVivo":
        p = cls.__new__(cls)
        p.grafo, p.autor, p.jugador, p.es_falsa = grafo, d["autor"], d["jugador"], d["es_falsa"]
        p.credibilidad_jugador = int(d["credibilidad_jugador"])
        p.estado, p.rumor, p.desmentido = dict(d["estado"]), dict(d["rumor"]), dict(d["desmentido"])
        p.enfriando, p.limitadas = dict(d["enfriando"]), list(d["limitadas"])
        p.alerta, p.t, p._acumulado, p.pasos = float(d["alerta"]), float(d["t"]), float(d["acumulado"]), int(d["pasos"])
        p.rng = random.Random()
        p.rng.setstate((d["rng"][0], tuple(d["rng"][1]), d["rng"][2]))
        return p


def _seguir(frente: dict[str, int], nuevos: dict[str, int]) -> dict[str, int]:
    """El frente del siguiente paso: los que siguen activos (un paso menos) y los recien llegados."""
    siguen = {u: n - 1 for u, n in frente.items() if n > 1}
    siguen.update(nuevos)
    return siguen
