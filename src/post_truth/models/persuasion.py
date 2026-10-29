"""Persuadir a alguien que cree un rumor (R13): lo usan el Barrio y los encuentros en la calle.

No se elige ninguna frase: el jugador se queda cerca y MANTIENE E. La conversacion es un arbol de dialogo N-ario
(data/persuasion.json) y la RAMA la decide su estado, no un menu: en cada nodo se toma la primera opcion cuyo
requisito cumple (evidencia reunida > credibilidad alta > nada). Cada etapa se completa llenando una barra cuya
velocidad depende del tipo de argumento; al llegar a una hoja, la persona queda convencida. Soltar a medias reinicia
la etapa, y si el argumento era debil ("nada") la persona se enoja.
Recorrido: O(1) por etapa y O(h) en total (h = profundidad del arbol); DFS (`mejor_camino`) solo para analizarlo.
"""
from __future__ import annotations

import json
from functools import lru_cache

from post_truth.config import RUTA_PERSUASION
from post_truth.structures.arbol_dialogo import NodoDialogo, Opcion

EVIDENCIA, CREDIBILIDAD, NADA = "evidencia", "credibilidad", "nada"


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_PERSUASION.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def arbol() -> NodoDialogo:
    return NodoDialogo.from_dict(datos()["arbol"])


def cumple(o: Opcion, evidencias: int, credibilidad: int) -> bool:
    if o.requiere == EVIDENCIA:
        return evidencias > 0
    if o.requiere == CREDIBILIDAD:
        return credibilidad >= datos()["umbral_credibilidad"]
    return True


def rama(nodo: NodoDialogo, evidencias: int, credibilidad: int) -> int:
    """La primera opcion que se puede usar (en el JSON van de la mas fuerte a la mas debil)."""
    return next(i for i, o in enumerate(nodo.opciones) if cumple(o, evidencias, credibilidad))


class Persuasion:
    def __init__(self, evidencias: int, credibilidad: int, camino: list[int] | None = None,
                 progreso: float = 0.0) -> None:
        self.evidencias, self.credibilidad = evidencias, credibilidad
        self.camino = list(camino or [])
        self.progreso = progreso       # 0..1 de la etapa actual
        self.convencido = False

    @property
    def nodo(self) -> NodoDialogo | None:
        return arbol().seguir(self.camino)

    @property
    def opcion(self) -> Opcion | None:
        n = self.nodo
        return None if n is None else n.opciones[rama(n, self.evidencias, self.credibilidad)]

    def avanzar(self, dt: float) -> bool:
        """E sigue apretada: llena la etapa. True cuando la persona queda convencida."""
        o = self.opcion
        if o is None or self.convencido:
            return self.convencido
        self.progreso += datos()["velocidad"][o.tipo] * dt
        if self.progreso >= 1.0:
            self.camino.append(rama(self.nodo, self.evidencias, self.credibilidad))
            self.progreso = 0.0
            self.convencido = o.hijo is None
        return self.convencido

    def soltar(self) -> bool:
        """Se dejo a medias: reinicia la etapa. True si se enoja (argumento debil y ya habia empezado)."""
        o, empezado = self.opcion, self.progreso > 0
        self.progreso = 0.0
        return empezado and o is not None and o.tipo == NADA

    def to_dict(self) -> dict:
        return {"evidencias": self.evidencias, "credibilidad": self.credibilidad, "camino": self.camino,
                "progreso": self.progreso, "convencido": self.convencido}

    @classmethod
    def from_dict(cls, d: dict) -> "Persuasion":
        p = cls(int(d["evidencias"]), int(d["credibilidad"]), d["camino"], float(d["progreso"]))
        p.convencido = bool(d.get("convencido", False))
        return p
