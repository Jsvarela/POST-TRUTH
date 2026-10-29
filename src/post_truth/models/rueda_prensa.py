"""Minijuego de la Alcaldia, "Rueda de prensa" (de accion): cinco periodistas en semicirculo. Uno se ilumina con
una pregunta y un anillo que se cierra (su tiempo); su icono dice que prueba pide: pista (triangulo), evidencia
(cuadrado), testimonio (circulo) o es una trampa (X). Se gira el foco (A/D o flechas) hacia el y se responde con
1 pista, 2 evidencia, 3 testimonio o Espacio "no puedo afirmarlo sin pruebas". Lo investigado es la MUNICION: cada
respuesta gasta una prueba de ese tipo, y sin ella no hay que responder. Con tiempo extendido los anillos van mas
lentos y nunca preguntan dos a la vez."""
from __future__ import annotations

import json
import random
from functools import lru_cache

from post_truth.config import RUTA_RUEDA
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar

PERIODISTAS = 5
TIPOS = {"1": "pista", "2": "evidencia", "3": "testimonio"}
TRAMPA = "trampa"


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_RUEDA.open("r", encoding="utf-8") as f:
        return json.load(f)


def posicion(i: int) -> float:
    """Donde esta el periodista i en el semicirculo: -1 (izquierda) .. 1 (derecha)."""
    return -1 + 2 * i / (PERIODISTAS - 1)


@registrar
class RuedaPrensa(Minijuego):
    id = "rueda"
    nombre = "Rueda de prensa"
    ayuda = ("Gira el foco (A/D o flechas) hacia el periodista que pregunta y responde con la prueba que pide: "
             "1 pista (triangulo), 2 evidencia (cuadrado), 3 testimonio (circulo). A una trampa (X), Espacio: "
             "no se afirma sin pruebas. Lo que investigaste es tu municion.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.rng = random.Random(4000 + contexto.dia)
        self.municion = {t: int(contexto.municion.get(t, 0)) for t in TIPOS.values()}
        self.foco = 0.0                  # -1 .. 1
        self.giro: set[str] = set()
        self.preguntas: list[list] = []  # [periodista, tipo, texto, restante, total]
        self.resultados: list[str] = []
        self.credito = float(datos()["credito_inicial"])
        self.t, self._proxima = 0.0, 0.8

    @property
    def duracion(self) -> float:
        return datos()["duracion"]

    @property
    def a_la_vez(self) -> int:
        return 1 if self.contexto.extendido or self.t < datos()["doble_desde"] else 2

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        sentido = ("der" in self.giro) - ("izq" in self.giro)
        self.foco = min(1.0, max(-1.0, self.foco + sentido * datos()["giro"] * dt))
        self._proxima -= dt
        if self._proxima <= 0 and len(self.preguntas) < self.a_la_vez and self.t < self.duracion - 2:
            libres = [i for i in range(PERIODISTAS) if i not in {p[0] for p in self.preguntas}]
            tipo = self.rng.choice((*TIPOS.values(), TRAMPA))
            total = datos()["tiempo_pregunta"] * self.contexto.ritmo
            self.preguntas.append([self.rng.choice(libres), tipo, self.rng.choice(datos()["preguntas"][tipo]),
                                   total, total])
            self._proxima = datos()["intervalo"] * self.contexto.ritmo
        quedan = []
        for p in self.preguntas:
            p[3] -= dt
            if p[3] <= 0:              # nadie respondio: parece que evade
                self._marcar("evade")
            else:
                quedan.append(p)
        self.preguntas = quedan

    def apuntada(self) -> list | None:
        """La pregunta del periodista hacia el que mira el foco (si esta lo bastante cerca)."""
        cerca = [p for p in self.preguntas if abs(posicion(p[0]) - self.foco) <= datos()["tolerancia"]]
        return min(cerca, key=lambda p: abs(posicion(p[0]) - self.foco), default=None)

    def accion(self, nombre: str) -> None:
        if self.terminado:
            return
        suelta = nombre.startswith("-")
        nombre = nombre.lstrip("-")
        if nombre in ("izq", "der"):
            (self.giro.discard if suelta else self.giro.add)(nombre)
            return
        if suelta or nombre not in (*TIPOS, "espacio"):
            return
        p = self.apuntada()
        if p is None:                  # responder al aire: nadie preguntaba ahi
            self._marcar("al_aire")
            return
        self.preguntas.remove(p)
        pide = p[1]
        if nombre == "espacio":        # "no puedo afirmarlo sin pruebas"
            honesto = pide == TRAMPA or self.municion[pide] == 0
            self._marcar("trampa_bien" if pide == TRAMPA else "honesto" if honesto else "evade")
            return
        tipo = TIPOS[nombre]
        if pide == TRAMPA:
            self._marcar("afirmo")     # respondio a una trampa como si fuera un hecho
        elif tipo != pide:
            self._marcar("equivocada")
        elif self.municion[tipo] == 0:
            self._marcar("sin_municion")
        else:
            self.municion[tipo] -= 1
            self._marcar("acierto")

    def _marcar(self, como: str) -> None:
        self.resultados.append(como)
        self.credito = max(0.0, min(100.0, self.credito + datos()["efectos"][como]))

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion

    def resultado(self) -> ResultadoMinijuego:
        buenas = self.resultados.count("acierto") + self.resultados.count("trampa_bien")
        afirmo = self.resultados.count("afirmo")
        malas = len(self.resultados) - buenas - self.resultados.count("honesto")
        impacto = Impact(trust=buenas // 2 - afirmo, verified_information=self.resultados.count("acierto") // 2,
                         misinformation=afirmo, score=buenas - malas)
        texto = f"Respondiste bien {buenas} preguntas; {malas} salieron mal (credito ante la prensa {round(self.credito)})."
        delta = max(-6, min(6, round((self.credito - datos()["credito_inicial"]) / 8)))
        return ResultadoMinijuego(impacto, delta, texto)

    def estado(self) -> dict:
        s = self.rng.getstate()
        return {"municion": self.municion, "foco": self.foco, "giro": sorted(self.giro), "preguntas": self.preguntas,
                "resultados": self.resultados, "credito": self.credito, "t": self.t, "proxima": self._proxima,
                "rng": [s[0], list(s[1]), s[2]]}

    def restaurar(self, estado: dict) -> None:
        self.municion = {k: int(v) for k, v in estado["municion"].items()}
        self.foco, self.giro = float(estado["foco"]), set(estado["giro"])
        self.preguntas = [list(p) for p in estado["preguntas"]]
        self.resultados, self.credito = list(estado["resultados"]), float(estado["credito"])
        self.t, self._proxima = float(estado["t"]), float(estado["proxima"])
        self.rng.setstate((estado["rng"][0], tuple(estado["rng"][1]), estado["rng"][2]))
