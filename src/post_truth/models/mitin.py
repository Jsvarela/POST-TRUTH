"""Minijuego de la Plaza, "Mitin": la multitud tiene una barra de animo; aparecen interrupciones y rumores y hay que
responder con el argumento adecuado en el momento justo (cuando el marcador pasa por la zona marcada). Los argumentos
con datos necesitan evidencia reunida antes. Con tiempo extendido no hay ritmo: cualquier momento vale."""
from __future__ import annotations

import json
from functools import lru_cache

from post_truth.config import RUTA_MITIN
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar

ACIERTO, DESTIEMPO, SIN_PRUEBAS, FALLO = "acierto", "destiempo", "sin_pruebas", "fallo"


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_MITIN.open("r", encoding="utf-8") as f:
        return json.load(f)


@registrar
class Mitin(Minijuego):
    id = "mitin"
    nombre = "Mitin"
    ayuda = ("Te interrumpen con rumores. Elige el argumento correcto (1, 2 o 3) cuando el marcador pase por la "
             "zona clara. Los argumentos con datos necesitan evidencia que hayas reunido antes.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        d = datos()
        n = len(d["interrupciones"])
        self.orden = [(contexto.dia + k) % n for k in range(d["por_mitin"])]   # cada dia empieza por otra
        self.resultados: list[str] = []
        self.animo = float(d["animo_inicial"])
        self.t = 0.0

    @property
    def sin_ritmo(self) -> bool:
        return self.contexto.extendido

    @property
    def periodo(self) -> float:
        return datos()["periodo"] * self.contexto.ritmo

    @property
    def limite(self) -> float:
        return self.periodo * datos()["ciclos"]

    @property
    def marcador(self) -> float:
        """0..1: donde va el marcador del ritmo."""
        return (self.t % self.periodo) / self.periodo

    @property
    def en_ventana(self) -> bool:
        a, b = datos()["ventana"]
        return self.sin_ritmo or a <= self.marcador <= b

    @property
    def actual(self) -> dict | None:
        return None if self.terminado else datos()["interrupciones"][self.orden[len(self.resultados)]]

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        if self.t >= self.limite:   # se quedo callado: el rumor queda en el aire
            self._marcar(FALLO)

    def accion(self, nombre: str) -> None:
        r = self.actual
        if r is None or nombre not in ("1", "2", "3"):
            return
        if int(nombre) - 1 != r["correcto"]:
            self._marcar(FALLO)
        elif r["requiere_evidencia"] and self.contexto.evidencias == 0:
            self._marcar(SIN_PRUEBAS)   # razon sin pruebas: la gente duda
        else:
            self._marcar(ACIERTO if self.en_ventana else DESTIEMPO)

    def _marcar(self, como: str) -> None:
        self.resultados.append(como)
        self.animo = max(0.0, min(100.0, self.animo + datos()["efectos"][como]))
        self.t = 0.0

    @property
    def terminado(self) -> bool:
        return len(self.resultados) >= len(self.orden)

    def resultado(self) -> ResultadoMinijuego:
        aciertos, destiempo, fallos = (self.resultados.count(c) for c in (ACIERTO, DESTIEMPO, FALLO))
        buenos = aciertos + destiempo
        impacto = Impact(trust=2 * aciertos + destiempo, misinformation=2 * fallos,
                         score=2 * aciertos + destiempo - 2 * fallos)
        rumor = fallos >= 2
        texto = f"Respondiste bien {buenos} de {len(self.orden)} interrupciones (animo {round(self.animo)})."
        if rumor:
            texto += " Lo que no aclaraste arranca un rumor en la red."
        return ResultadoMinijuego(impacto, 2 * aciertos - 2 * fallos, texto, rumor)

    def estado(self) -> dict:
        return {"orden": self.orden, "resultados": self.resultados, "animo": self.animo, "t": self.t}

    def restaurar(self, estado: dict) -> None:
        self.orden, self.resultados = list(estado["orden"]), list(estado["resultados"])
        self.animo, self.t = float(estado["animo"]), float(estado["t"])
