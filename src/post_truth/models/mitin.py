"""Minijuego "Mitin" (de disparos): los rumores suben como globos que zigzaguean hacia el escenario. Se apunta una mira
(raton, o WASD/flechas) y se dispara (clic o Espacio) con la municion que pide la forma del globo: 1 dato (cuadrado),
2 pregunta (circulo), 3 calma (triangulo). El disparo VIAJA: hay que adelantarse al globo. La municion equivocada
rebota y gasta la recarga. Si un globo llega arriba, el rumor se queda en el aire (3 o mas arrancan un rumor). Los
datos necesitan evidencia reunida antes. Con tiempo extendido los globos suben mas lento y son mas faciles de tocar.
Todo en coordenadas normalizadas del area (0..1), sin pygame."""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache

from post_truth.config import RUTA_MITIN
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar

ACIERTO, SIN_PRUEBAS, FALLO, LLEGA = "acierto", "sin_pruebas", "fallo", "llega"
TIPOS = {"1": "dato", "2": "pregunta", "3": "calma"}
CANON = (0.5, 1.0)        # de donde sale el disparo (abajo al centro)
ASPECTO = 600 / 364       # ancho / alto del area: las distancias se miden redondas en pantalla
MOVER = {"izq": (-1, 0), "der": (1, 0), "arriba": (0, -1), "abajo": (0, 1)}


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_MITIN.open("r", encoding="utf-8") as f:
        return json.load(f)


def distancia(a, b) -> float:
    return math.hypot((a[0] - b[0]) * ASPECTO, a[1] - b[1])


@registrar
class Mitin(Minijuego):
    id = "mitin"
    nombre = "Mitin"
    usa_raton = True
    ayuda = ("Los rumores suben como globos. Apunta con el raton (o WASD), elige la municion que pide su forma "
             "(1 dato cuadrado, 2 pregunta circulo, 3 calma triangulo) y dispara con clic o Espacio: el disparo "
             "tarda en llegar, adelantate. Los datos necesitan evidencia reunida.")
    pasos_tutorial = ("Los rumores suben como globos: que no lleguen arriba.",
                      "Mira su forma: cuadrado pide un dato, circulo una pregunta, triangulo calma.",
                      "Elige esa municion con 1, 2 o 3.",
                      "Apunta con el raton (o WASD) un poco por delante del globo: se mueve.",
                      "Dispara con clic o Espacio. Con la municion equivocada el disparo rebota.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.rng = random.Random(2000 + contexto.dia)
        self.globos: list[list] = []      # [x de partida, y (1 abajo .. 0 arriba), tipo, grito, fase, rapidez]
        self.balas: list[list] = []       # [x, y, dx, dy, tipo] (dx, dy en area/s)
        self.mira = [0.5, 0.5]
        self.mover: set[str] = set()
        self.municion = "pregunta"
        self.recarga = 0.0
        self.resultados: list[str] = []
        self.animo = float(datos()["animo_inicial"])
        self.t, self._proximo = 0.0, 0.4

    @property
    def duracion(self) -> float:
        return datos()["duracion"]

    @property
    def subida(self) -> float:
        return datos()["subida"] / self.contexto.ritmo

    @property
    def radio(self) -> float:
        return datos()["disparo"]["radio"] * (1.4 if self.contexto.extendido else 1.0)

    def posicion(self, g: list, t: float | None = None) -> tuple[float, float]:
        """Donde esta (o estara, con `t`) el globo: sube y zigzaguea."""
        dt = 0.0 if t is None else t - self.t
        y = g[1] - self.subida * g[5] * dt
        x = g[0] + datos()["disparo"]["zigzag"] * math.sin((self.t + dt) * 2.2 + g[4])
        return min(0.97, max(0.03, x)), y

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        self.recarga = max(0.0, self.recarga - dt)
        dx = sum(MOVER[m][0] for m in self.mover)
        dy = sum(MOVER[m][1] for m in self.mover)
        v = datos()["disparo"]["mira"] * dt
        self.mira = [min(1.0, max(0.0, self.mira[0] + dx * v / ASPECTO)), min(1.0, max(0.0, self.mira[1] + dy * v))]
        self._proximo -= dt
        if self._proximo <= 0 and self.t < self.duracion - 2:
            r = self.rng.choice(datos()["interrupciones"])
            self.globos.append([round(self.rng.uniform(0.12, 0.88), 3), 1.0, r["tipo"], r["grito"],
                                round(self.rng.uniform(0, 6.28), 2), round(self.rng.uniform(0.8, 1.25), 2)])
            self._proximo = datos()["intervalo"] * self.contexto.ritmo
        quedan = []
        for g in self.globos:
            g[1] -= self.subida * g[5] * dt
            if g[1] <= 0:              # llego al escenario: el rumor queda en el aire
                self._marcar(LLEGA)
            else:
                quedan.append(g)
        self.globos = quedan
        self._mover_balas(dt)

    def _mover_balas(self, dt: float) -> None:
        vivas = []
        for b in self.balas:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            g = next((g for g in self.globos if distancia(self.posicion(g), b) <= self.radio), None)
            if g is not None:
                if g[2] == b[4]:       # la respuesta que pedia: revienta
                    self.globos.remove(g)
                    self._marcar(SIN_PRUEBAS if b[4] == "dato" and self.contexto.evidencias == 0 else ACIERTO)
                else:                  # municion equivocada: rebota
                    self._marcar(FALLO)
                continue
            if -0.05 <= b[0] <= 1.05 and -0.05 <= b[1] <= 1.05:
                vivas.append(b)        # el que sale del area se pierde sin castigo: solo gasto la recarga
        self.balas = vivas

    def accion(self, nombre: str) -> None:
        if self.terminado:
            return
        suelta = nombre.startswith("-")
        nombre = nombre.lstrip("-")
        if nombre in MOVER:
            (self.mover.discard if suelta else self.mover.add)(nombre)
        elif suelta:
            return
        elif nombre in TIPOS:
            self.municion = TIPOS[nombre]
        elif nombre.startswith("apuntar:"):
            _, x, y = nombre.split(":")
            self.mira = [min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))]
        elif nombre in ("espacio", "disparo") and self.recarga <= 0:
            d = distancia(self.mira, CANON)
            if d > 0:
                v = datos()["disparo"]["velocidad"] / d   # en "distancias" por segundo, redondo en pantalla
                self.balas.append([CANON[0], CANON[1], (self.mira[0] - CANON[0]) * v, (self.mira[1] - CANON[1]) * v,
                                   self.municion])
                self.recarga = datos()["disparo"]["cadencia"]

    def demo(self) -> list[str]:
        """Apunta por delante del globo mas alto con la municion que pide y dispara cuando la recarga lo deja."""
        subidos = [g for g in self.globos if g[1] < 0.75]   # espera a que suba: asi se ve que hay que adelantarse
        if not subidos or self.recarga > 0:
            return []
        g = min(subidos, key=lambda g: g[1])
        t = self.t
        for _ in range(4):   # adelantarse: donde estara cuando llegue el disparo
            x, y = self.posicion(g, t)
            t = self.t + distancia((x, y), CANON) / datos()["disparo"]["velocidad"]
        x, y = self.posicion(g, t)
        tecla = next(k for k, v in TIPOS.items() if v == g[2])
        return [tecla, f"apuntar:{x:.4f}:{y:.4f}", "disparo"]

    def _marcar(self, como: str) -> None:
        self.ecos.append("acierto" if como in (ACIERTO, SIN_PRUEBAS) else "error")
        self.resultados.append(como)
        self.animo = max(0.0, min(100.0, self.animo + datos()["efectos"][como]))

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion

    def resultado(self) -> ResultadoMinijuego:
        aciertos, sin, fallos = (self.resultados.count(c) for c in (ACIERTO, SIN_PRUEBAS, FALLO))
        llegan = self.resultados.count(LLEGA)
        malos = fallos + llegan
        impacto = Impact(trust=aciertos // 2 + sin // 3, misinformation=llegan, score=aciertos - malos)
        rumor = llegan >= 3
        texto = f"Reventaste {aciertos + sin} rumores; {llegan} llegaron arriba (animo {round(self.animo)})."
        if rumor:
            texto += " Lo que no aclaraste arranca un rumor en la red."
        return ResultadoMinijuego(impacto, max(-6, min(6, (aciertos - 2 * malos) // 2)), texto, rumor)

    def estado(self) -> dict:
        s = self.rng.getstate()
        return {"globos": self.globos, "balas": self.balas, "mira": self.mira, "mover": sorted(self.mover),
                "municion": self.municion, "recarga": self.recarga, "resultados": self.resultados,
                "animo": self.animo, "t": self.t, "proximo": self._proximo, "rng": [s[0], list(s[1]), s[2]]}

    def restaurar(self, estado: dict) -> None:
        self.globos, self.balas = [list(g) for g in estado["globos"]], [list(b) for b in estado.get("balas", [])]
        self.mira, self.mover = list(estado.get("mira", [0.5, 0.5])), set(estado.get("mover", []))
        self.municion, self.recarga = estado.get("municion", "pregunta"), float(estado.get("recarga", 0.0))
        self.resultados = list(estado["resultados"])
        self.animo, self.t, self._proximo = float(estado["animo"]), float(estado["t"]), float(estado["proximo"])
        self.rng.setstate((estado["rng"][0], tuple(estado["rng"][1]), estado["rng"][2]))
