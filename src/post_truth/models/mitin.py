"""Minijuego de la Plaza, "Mitin" (de accion): los rumores suben desde la multitud como globos hacia el escenario.
Cada globo pide una respuesta segun su forma: 1 dato (cuadrado), 2 pregunta (circulo) o 3 calma (triangulo). La
tecla revienta el globo de ese tipo que este mas cerca del escenario; si llega arriba, el rumor se queda en el aire.
Los globos de dato necesitan evidencia reunida antes. Con tiempo extendido suben mas lento."""
from __future__ import annotations

import json
import random
from functools import lru_cache

from post_truth.config import RUTA_MITIN
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar

ACIERTO, SIN_PRUEBAS, FALLO, LLEGA = "acierto", "sin_pruebas", "fallo", "llega"
TIPOS = {"1": "dato", "2": "pregunta", "3": "calma"}
COLUMNAS = 5


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_MITIN.open("r", encoding="utf-8") as f:
        return json.load(f)


@registrar
class Mitin(Minijuego):
    id = "mitin"
    nombre = "Mitin"
    ayuda = ("Los rumores suben como globos hacia el escenario. Revientalos con la respuesta que pide su forma: "
             "1 dato (cuadrado), 2 pregunta (circulo), 3 calma (triangulo). Los datos necesitan evidencia reunida.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.rng = random.Random(2000 + contexto.dia)
        self.globos: list[list] = []      # [columna, altura 1 abajo .. 0 escenario, tipo, grito]
        self.resultados: list[str] = []
        self.animo = float(datos()["animo_inicial"])
        self.t, self._proximo = 0.0, 0.4

    @property
    def duracion(self) -> float:
        return datos()["duracion"]

    @property
    def subida(self) -> float:
        return datos()["subida"] / self.contexto.ritmo

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        self._proximo -= dt
        if self._proximo <= 0 and self.t < self.duracion - 2:
            r = self.rng.choice(datos()["interrupciones"])
            self.globos.append([self.rng.randrange(COLUMNAS), 1.0, r["tipo"], r["grito"]])
            self._proximo = datos()["intervalo"] * self.contexto.ritmo
        quedan = []
        for g in self.globos:
            g[1] -= self.subida * dt
            if g[1] <= 0:              # llego al escenario: el rumor queda en el aire
                self._marcar(LLEGA)
            else:
                quedan.append(g)
        self.globos = quedan

    def accion(self, nombre: str) -> None:
        if self.terminado or nombre not in TIPOS:
            return
        tipo = TIPOS[nombre]
        candidatos = [g for g in self.globos if g[2] == tipo]
        if not candidatos:             # respuesta equivocada: no habia ningun globo de ese tipo
            self._marcar(FALLO)
            return
        g = min(candidatos, key=lambda x: x[1])   # el mas cerca del escenario
        self.globos.remove(g)
        self._marcar(SIN_PRUEBAS if tipo == "dato" and self.contexto.evidencias == 0 else ACIERTO)

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
        texto = f"Reventaste {aciertos + sin} rumores; {llegan} llegaron al escenario (animo {round(self.animo)})."
        if rumor:
            texto += " Lo que no aclaraste arranca un rumor en la red."
        return ResultadoMinijuego(impacto, max(-6, min(6, (aciertos - 2 * malos) // 2)), texto, rumor)

    def estado(self) -> dict:
        s = self.rng.getstate()
        return {"globos": self.globos, "resultados": self.resultados, "animo": self.animo, "t": self.t,
                "proximo": self._proximo, "rng": [s[0], list(s[1]), s[2]]}

    def restaurar(self, estado: dict) -> None:
        self.globos, self.resultados = [list(g) for g in estado["globos"]], list(estado["resultados"])
        self.animo, self.t, self._proximo = float(estado["animo"]), float(estado["t"]), float(estado["proximo"])
        self.rng.setstate((estado["rng"][0], tuple(estado["rng"][1]), estado["rng"][2]))
