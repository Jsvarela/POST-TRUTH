"""Contenido de la ayuda (F2 y el menu): las secciones de data/ayuda.json con sus numeros tomados de las constantes
del juego, asi la ayuda dice lo mismo que el juego aunque cambie un valor."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from post_truth.config import RUTA_AYUDA
from post_truth.models import Role, posts, roles
from post_truth import sesion as ses
from post_truth.structures.propagacion_vivo import ENFRIAMIENTO


@dataclass(frozen=True)
class Seccion:
    id: str
    titulo: str
    lineas: tuple[str, ...]


def valores() -> dict[str, object]:
    habilidades = "\n".join(f"- {r.value}: {h.nombre}. {h.descripcion} ({round(h.enfriamiento)} s)"
                            for r, h in ((r, roles.HABILIDADES[r]) for r in Role))
    return {"dias": ses.DIAS, "duracion_dia": round(ses.DURACION_DIA),
            "tiempo_viral": round(ses.TIEMPO_VIRAL), "ritmo_telefono": round(ses.RITMO_TELEFONO * 100),
            "ritmo_rumor": round(ses.RITMO_RUMOR_TELEFONO * 100), "viral": round(ses.VIRAL_EN_VIVO * 100),
            "onda": round(ENFRIAMIENTO["onda"]), "enfriamiento_post": posts.reglas().reglas["enfriamiento"],
            "enfriamiento_aliado": round(roles.ENFRIAMIENTO_ALIADO), "factor": ses.FACTOR_TIEMPO_EXTENDIDO,
            "habilidades": habilidades}


@lru_cache(maxsize=1)
def secciones() -> tuple[Seccion, ...]:
    with RUTA_AYUDA.open("r", encoding="utf-8") as f:
        datos = json.load(f)
    v = valores()
    return tuple(Seccion(s["id"], s["titulo"], tuple(l for t in s["texto"] for l in t.format(**v).split("\n")))
                 for s in datos["secciones"])


def indice(id: str) -> int:
    return next((i for i, s in enumerate(secciones()) if s.id == id), 0)
