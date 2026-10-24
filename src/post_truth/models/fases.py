"""Fases electorales (R9): agrupan los dias de la campana y dicen que cambia en el grafo de la ciudad
(zonas que abren, fronteras que una protesta cierra segun los indicadores, umbrales de crisis). Logica pura."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from post_truth.config import RUTA_FASES


@dataclass(frozen=True)
class Fase:
    id: str
    nombre: str
    dias: tuple[int, ...]          # dias de la campana (desde 1)
    abre: tuple[str, ...]          # zonas que se insertan en el grafo al empezar
    descripcion: str
    variante: str | None = None    # variante del mapa (p. ej. "noche")


@dataclass(frozen=True)
class Protesta:
    """Cierra la frontera a-b si `indicador` pasa de `cierra`; la reabre si baja de `reabre` (histeresis: entre
    los dos umbrales no cambia, asi no se abre y se cierra a cada rato)."""
    a: str
    b: str
    indicador: str
    cierra: int
    reabre: int

    @property
    def clave(self) -> str:
        return "|".join(sorted((self.a, self.b)))


@dataclass(frozen=True)
class ReglasFases:
    centro: str                    # desde donde se mide la conectividad (BFS)
    fases: tuple[Fase, ...]
    zonas_nuevas: dict[str, dict]
    protestas: tuple[Protesta, ...]
    crisis_entra: int
    crisis_sale: int

    def indice_del_dia(self, dia: int) -> int:
        """`dia` desde 0; despues del ultimo dia definido sigue la ultima fase."""
        return next((i for i, f in enumerate(self.fases) if dia + 1 in f.dias), len(self.fases) - 1)

    @classmethod
    def from_dict(cls, d: dict) -> "ReglasFases":
        fases = tuple(Fase(f["id"], f["nombre"], tuple(f["dias"]), tuple(f.get("abre", [])), f.get("descripcion", ""),
                           f.get("variante")) for f in d["fases"])
        dias = [x for f in fases for x in f.dias]
        if sorted(dias) != list(range(1, len(dias) + 1)):
            raise ValueError("Las fases deben cubrir los dias 1..N una sola vez y en orden")
        for f in fases:
            for z in f.abre:
                if z not in d["zonas_nuevas"]:
                    raise ValueError(f"La fase {f.id} abre una zona sin definir: {z}")
        protestas = tuple(Protesta(*p["arista"], p["indicador"], p["cierra"], p["reabre"]) for p in d["protestas"])
        if any(p.reabre >= p.cierra for p in protestas) or d["crisis"]["sale"] >= d["crisis"]["entra"]:
            raise ValueError("Cada umbral de salida debe quedar por debajo del de entrada")
        return cls(d["centro"], fases, dict(d["zonas_nuevas"]), protestas, d["crisis"]["entra"], d["crisis"]["sale"])

    @property
    def dias(self) -> int:
        return sum(len(f.dias) for f in self.fases)


@lru_cache(maxsize=1)
def reglas() -> ReglasFases:
    with RUTA_FASES.open("r", encoding="utf-8") as f:
        return ReglasFases.from_dict(json.load(f))
