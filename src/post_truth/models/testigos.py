"""Testigos de una noticia (R6): quienes estan en el lugar (uno dice la verdad, otro exagera, otro se contradice) y
los testigos de las evidencias de otras zonas. El interrogatorio es un arbol de dialogo N-ario armado con plantillas
(data/testigos.json): cada pregunta lleva a una respuesta que ofrece las preguntas que faltan."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache

from post_truth.config import RUTA_TESTIGOS
from post_truth.models.pistas import Evidencia, TipoEvidencia
from post_truth.structures.arbol_dialogo import NodoDialogo, Opcion
from post_truth.structures.grafo_social import Ciudadano

VERAZ, EXAGERA, CONTRADICE, ZONA = "veraz", "exagera", "contradice", "zona"
FIABLES = (VERAZ, ZONA)
ORDEN = (VERAZ, EXAGERA, CONTRADICE)   # a quien le toca cada fiabilidad entre los presentes
PREGUNTAS = ("version", "fuente", "confirma")


@lru_cache(maxsize=1)
def plantillas() -> dict:
    with RUTA_TESTIGOS.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class Testigo:
    id: str
    nombre: str
    lugar: str                 # donde esta (los de otras zonas hay que ir a verlos)
    fiabilidad: str            # veraz | exagera | contradice | zona
    evidencia: Evidencia | None = None

    @property
    def fiable(self) -> bool:
        return self.fiabilidad in FIABLES


def testigos(evento_id: str, lugar: str, presentes: list[Ciudadano], evidencias: tuple[Evidencia, ...]) -> list[Testigo]:
    """Los del lugar reciben su fiabilidad por un hash estable (no toca el azar de la partida); luego los testigos
    de las evidencias de otras zonas."""
    def clave(c: Ciudadano) -> str:
        return hashlib.md5(f"testigo:{evento_id}:{c.id}".encode()).hexdigest()
    locales = [Testigo(c.id, c.nombre, lugar, f) for c, f in zip(sorted(presentes, key=clave), ORDEN)]
    lejanos = [Testigo(e.id, e.titulo, e.lugar, ZONA, e) for e in evidencias
               if e.tipo is TipoEvidencia.TESTIGO and e.lugar != lugar]
    return locales + lejanos


def respuesta(t: Testigo, pregunta: str, es_falsa: bool, lugar_dato: str) -> str:
    r = plantillas()["respuestas"][t.fiabilidad]
    if t.fiabilidad == VERAZ and pregunta == "version":
        return r["version_falsa" if es_falsa else "version_verdadera"]
    texto = r[pregunta]
    if t.evidencia is not None:
        texto = texto.format(hallazgo=t.evidencia.hallazgo, titulo=t.evidencia.titulo.lower())
    return texto.format(lugar=lugar_dato.capitalize())


def arbol(t: Testigo, es_falsa: bool, lugar_dato: str) -> NodoDialogo:
    """Raiz: el saludo; cada pregunta lleva a su respuesta, que ofrece las preguntas que faltan y "Gracias"."""
    p = plantillas()

    def nodo(texto: str, faltan: tuple[str, ...]) -> NodoDialogo:
        opciones = [Opcion(p["preguntas"][q], q, nodo(respuesta(t, q, es_falsa, lugar_dato),
                                                      tuple(x for x in faltan if x != q))) for q in faltan]
        return NodoDialogo(t.nombre, texto, opciones + [Opcion(p["cerrar"], "cerrar")])
    return nodo(p["saludo"][t.fiabilidad], PREGUNTAS)
