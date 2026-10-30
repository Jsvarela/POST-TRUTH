"""Reparto (L4): los candidatos con su retrato (data/reparto.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from post_truth.config import RUTA_REPARTO

PEINADOS = ("corto", "largo", "rizado", "recogido")
ACCESORIOS = ("corbata", "aretes", "lentes", "bufanda", "barba")
TONOS = 2
COLORES = 4


@dataclass(frozen=True)
class AspectoRetrato:
    piel: int
    cabello: int
    peinado: str
    accesorio: str
    color: int

    def __post_init__(self) -> None:
        if not (0 <= self.piel < TONOS and 0 <= self.cabello < TONOS and 0 <= self.color < COLORES):
            raise ValueError(f"Aspecto fuera de rango: {self}")
        if self.peinado not in PEINADOS:
            raise ValueError(f"Peinado desconocido: {self.peinado}")
        if self.accesorio not in ACCESORIOS:
            raise ValueError(f"Accesorio desconocido: {self.accesorio}")


@dataclass(frozen=True)
class Candidato:
    id: str
    nombre: str
    lema: str
    propuesta: str
    aspecto: AspectoRetrato


@lru_cache(maxsize=1)
def candidatos() -> tuple[Candidato, ...]:
    with RUTA_REPARTO.open("r", encoding="utf-8") as f:
        return tuple(Candidato(c["id"], c["nombre"], c["lema"], c["propuesta"], AspectoRetrato(**c["aspecto"]))
                     for c in json.load(f)["candidatos"])


def candidato(id: str) -> Candidato:
    return next(c for c in candidatos() if c.id == id)
