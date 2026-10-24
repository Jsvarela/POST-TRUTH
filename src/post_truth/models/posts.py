"""Crear posts (R4): el jugador arma una publicacion con piezas y un modelo de reglas (data/posts.json) calcula
veracidad, alcance, riesgo de conflicto y efecto en la convivencia segun la pieza y el rol. Logica pura."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from post_truth.config import RUTA_POSTS

PIEZAS = ("formato", "titular", "imagen", "fuente", "tono")   # en el orden en que se arman en el telefono
_LISTAS = {"titular": "titulares", "imagen": "imagenes", "fuente": "fuentes", "tono": "tonos"}
ALCANCE_LLENO = 4.0   # multiplicador que se muestra como alcance 100


@dataclass(frozen=True)
class Post:
    formato: str
    titular: str
    imagen: str
    fuente: str
    tono: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Evaluacion:
    veracidad: int        # 0-100
    alcance: float        # multiplica la transmision en la red (1 = normal)
    riesgo: int           # 0-100: riesgo de conflicto
    convivencia: int      # cambio directo en la convivencia
    es_falsa: bool
    desmiente: bool       # formato de desmentido (Candidato)

    @property
    def alcance_100(self) -> int:
        return min(100, round(100 * self.alcance / ALCANCE_LLENO))


def _acotar(x: float) -> int:
    return round(max(0, min(100, x)))


class ReglasPosts:
    def __init__(self, datos: dict) -> None:
        self.datos = datos
        self.reglas = datos["reglas"]

    @classmethod
    def cargar(cls, ruta: str | Path = RUTA_POSTS) -> "ReglasPosts":
        with Path(ruta).open("r", encoding="utf-8") as f:
            return cls(json.load(f))

    def opciones(self, pieza: str, rol: str) -> list[dict]:
        """Las opciones de una pieza; los formatos dependen del rol (Role.name)."""
        return self.datos["formatos"][rol] if pieza == "formato" else self.datos[_LISTAS[pieza]]

    def _pieza(self, pieza: str, rol: str, id: str) -> dict:
        for o in self.opciones(pieza, rol):
            if o["id"] == id:
                return o
        raise ValueError(f"{pieza} desconocido para {rol}: {id!r}")

    def evaluar(self, post: Post, rol: str) -> Evaluacion:
        f, ti, im = self._pieza("formato", rol, post.formato), self._pieza("titular", rol, post.titular), \
            self._pieza("imagen", rol, post.imagen)
        fu, to = self._pieza("fuente", rol, post.fuente), self._pieza("tono", rol, post.tono)
        veracidad = ti["veracidad"] + im["veracidad"] + fu["veracidad"] + f.get("veracidad", 0)
        if f.get("requiere_fuente") and post.fuente != f["requiere_fuente"]:   # una nota sin fuente no es nota
            veracidad -= f["penalizacion"]
        veracidad = _acotar(veracidad)
        alcance = ti["gancho"] * im["gancho"] * fu["alcance"] * to["alcance"] * f.get("alcance", 1.0)
        riesgo = _acotar(to["conflicto"] + f.get("conflicto", 0) + 0.3 * (100 - veracidad))
        es_falsa = veracidad < self.reglas["umbral_falsa"]
        convivencia = to["convivencia"] + f.get("convivencia", 0) + (1 if veracidad >= 70 else -2 if es_falsa else 0)
        return Evaluacion(veracidad, round(alcance, 3), riesgo, convivencia, es_falsa, bool(f.get("desmiente")))

    def credibilidad(self, post: Post, ev: Evaluacion, viral: bool) -> int:
        """Lo que cambia la credibilidad DESPUES de publicar: sin fuente, agresivo o falso cuesta (mas si se hizo
        viral); veraz, verificable y sin agresividad da un poco."""
        r = self.reglas
        costo = (r["costo_sin_fuente"] * (post.fuente == "ninguna") + r["costo_agresivo"] * (post.tono == "agresivo")
                 + r["costo_falsa"] * ev.es_falsa)
        if viral:
            costo *= r["multiplicador_viral"]
        premio = r["premio_veraz_verificable"] if (not costo and post.fuente == "verificable") else 0
        return round(premio - costo)

    def conflictos(self, ev: Evaluacion, fraccion_alcanzada: float) -> int:
        """Conflictos que deja en la ciudad: el riesgo por cuanto de la red alcanzo."""
        return round(self.reglas["conflictos_maximo"] * ev.riesgo / 100 * fraccion_alcanzada)


@lru_cache(maxsize=1)
def reglas() -> ReglasPosts:
    return ReglasPosts.cargar()
