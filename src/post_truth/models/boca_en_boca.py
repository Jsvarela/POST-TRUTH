"""Minijuego del Barrio, "De boca en boca" (de accion): el chisme salta de casa en casa por las conexiones del
barrio (un grafo pequeno, como el social) y se ve viajar. El jugador corre (WASD o flechas) hasta un vecino que lo
cree y mantiene E cerca para convencerlo (models/persuasion.py: la rama del arbol sale de la evidencia y la
credibilidad). Un vecino convencido ya no lo cree ni lo pasa. Con tiempo extendido el chisme salta mas lento."""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache

from post_truth.config import RUTA_BARRIO
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar
from post_truth.models.persuasion import Persuasion

SIN, CREE, CONVENCIDA, ENOJADA = "sin", "cree", "convencida", "enojada"
ASPECTO = 540 / 214   # ancho/alto del barrio en pantalla: el alcance es un circulo y se camina igual en x y en y
DIRECCIONES = {"izq": (-1, 0), "der": (1, 0), "arriba": (0, -1), "abajo": (0, 1)}


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_BARRIO.open("r", encoding="utf-8") as f:
        return json.load(f)


@registrar
class BocaEnBoca(Minijuego):
    id = "boca"
    nombre = "De boca en boca"
    ayuda = ("El chisme salta de casa en casa. Corre hasta quien lo cree (WASD o flechas) y manten E cerca para "
             "convencerlo. Con evidencia y credibilidad convences mas rapido; si sueltas un argumento debil, se enoja.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.rng = random.Random(3000 + contexto.dia)
        n = len(datos()["casas"])
        self.casas = [SIN] * n
        self.casas[self.rng.randrange(n)] = CREE
        self.rumor = self.rng.choice(datos()["rumores"])
        self.jugador = [0.5, 0.45]
        self.dirs: set[str] = set()
        self.hablando = False
        self.charla: tuple[int, Persuasion] | None = None
        self.saltos: list[tuple[int, int]] = []   # (de, a) de los ultimos saltos, para dibujarlos viajando
        self.t, self._salto, self._brote = 0.0, self.intervalo, datos()["brote"] * contexto.ritmo

    @property
    def intervalo(self) -> float:
        return datos()["salto"] * self.contexto.ritmo

    @property
    def duracion(self) -> float:
        return datos()["duracion"]

    def cercana(self) -> int | None:
        """La casa que cree el chisme mas cerca del jugador, si esta a su alcance."""
        x, y = self.jugador
        candidatas = [(math.dist((x * ASPECTO, y), (c["pos"][0] * ASPECTO, c["pos"][1])), i)
                      for i, c in enumerate(datos()["casas"]) if self.casas[i] == CREE]
        d, i = min(candidatas, default=(math.inf, None))
        return i if d <= datos()["radio"] * ASPECTO else None

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        dx = sum(DIRECCIONES[d][0] for d in self.dirs)
        dy = sum(DIRECCIONES[d][1] for d in self.dirs)
        if dx or dy:
            n = math.hypot(dx, dy)
            v = datos()["velocidad"] * dt / n
            self.jugador = [min(1.0, max(0.0, self.jugador[0] + dx * v / ASPECTO)),
                            min(1.0, max(0.0, self.jugador[1] + dy * v))]
        self._salto -= dt
        if self._salto <= 0:
            self._saltar()
            self._salto = self.intervalo
        self._brote -= dt
        if self._brote <= 0:   # alguien de afuera lo reenvia: vuelve a entrar al barrio
            sin = [i for i, e in enumerate(self.casas) if e == SIN]
            if sin:
                self.casas[self.rng.choice(sin)] = CREE
            self._brote = datos()["brote"] * self.contexto.ritmo
        self._conversar(dt)

    def _saltar(self) -> None:
        """Una arista por salto: de quien lo cree (o se enojo) a un vecino que aun no sabe (BFS de a un paso)."""
        pares = [(a, b) for x, y in datos()["conexiones"] for a, b in ((x, y), (y, x))]
        posibles = [(a, b) for a, b in pares if self.casas[a] in (CREE, ENOJADA) and self.casas[b] == SIN]
        if posibles:
            a, b = self.rng.choice(sorted(posibles))
            self.casas[b] = CREE
            self.saltos = (self.saltos + [(a, b)])[-4:]

    def _conversar(self, dt: float) -> None:
        cerca = self.cercana() if self.hablando else None
        if self.charla is not None and self.charla[0] != cerca:   # se alejo o solto E
            casa, p = self.charla
            if p.soltar() and self.casas[casa] == CREE:
                self.casas[casa] = ENOJADA
            self.charla = None
        if cerca is None:
            return
        if self.charla is None:
            self.charla = (cerca, Persuasion(self.contexto.evidencias, self.contexto.credibilidad))
        if self.charla[1].avanzar(dt):
            self.casas[cerca] = CONVENCIDA
            self.charla = None

    def accion(self, nombre: str) -> None:
        if self.terminado:
            return
        suelta = nombre.startswith("-")
        nombre = nombre.lstrip("-")
        if nombre in DIRECCIONES:
            (self.dirs.discard if suelta else self.dirs.add)(nombre)
        elif nombre == "hablar":
            self.hablando = not suelta

    def contar(self, estado: str) -> int:
        return self.casas.count(estado)

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion or SIN not in self.casas and CONVENCIDA not in self.casas   # o le llego a todos

    def resultado(self) -> ResultadoMinijuego:
        c, k, e = self.contar(CONVENCIDA), self.contar(CREE), self.contar(ENOJADA)
        impacto = Impact(coexistence=c, misinformation=k, conflicts=e, score=2 * c - k - e)
        rumor = e >= 2
        texto = f"Convenciste a {c} vecinos; {k} aun lo creen y {e} se enojaron."
        if rumor:
            texto += " Los que se enojaron lo riegan por la red."
        return ResultadoMinijuego(impacto, max(-6, min(6, c - e - (2 if k >= len(self.casas) - 1 else 0))), texto, rumor)

    def estado(self) -> dict:
        s = self.rng.getstate()
        return {"casas": self.casas, "rumor": self.rumor, "jugador": self.jugador, "dirs": sorted(self.dirs),
                "hablando": self.hablando, "saltos": self.saltos, "t": self.t, "salto": self._salto, "brote": self._brote,
                "charla": None if self.charla is None else [self.charla[0], self.charla[1].to_dict()],
                "rng": [s[0], list(s[1]), s[2]]}

    def restaurar(self, estado: dict) -> None:
        self.casas, self.rumor = list(estado["casas"]), estado["rumor"]
        self.jugador, self.dirs = list(estado["jugador"]), set(estado["dirs"])
        self.hablando, self.saltos = bool(estado["hablando"]), [tuple(x) for x in estado["saltos"]]
        self.t, self._salto, self._brote = float(estado["t"]), float(estado["salto"]), float(estado["brote"])
        c = estado["charla"]
        self.charla = None if c is None else (int(c[0]), Persuasion.from_dict(c[1]))
        self.rng.setstate((estado["rng"][0], tuple(estado["rng"][1]), estado["rng"][2]))
