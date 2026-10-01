"""Modelo: pistas de una noticia, investigacion con energia y texto de consecuencia. Logica pura.

IDEA DE JUEGO
    La tarjeta de una publicacion tiene partes revisables (autor, fuente, fecha, imagen, texto,
    estadisticas). Cada una puede esconder una PISTA que apunta a que la noticia es falsa, a que
    es verdadera o que no prueba nada (neutra). Investigar una pista revela su hallazgo y gasta
    ENERGIA; hay mas pistas que energia, asi que el jugador debe elegir que revisar antes de
    decidir. Las pistas no cambian los puntajes: cambian lo que el jugador SABE y el texto de la
    consecuencia (decidir con o sin evidencia no se cuenta igual).

Energia y no rondas: investigar una noticia falsa no debe delatarla (si costara una ronda, solo los
rumores de noticias falsas avanzarian y el mapa lo mostraria).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

ENERGIA_POR_NOTICIA = 3     # puntos que se recargan al abrir cada publicacion
COSTO_MIN, COSTO_MAX = 1, 3


class ZonaTarjeta(Enum):
    """Parte de la tarjeta de Civitas que se puede revisar."""
    AUTOR = "autor"
    FUENTE = "fuente"
    FECHA = "fecha"
    IMAGEN = "imagen"
    TEXTO = "texto"
    ESTADISTICAS = "estadisticas"


class Senal(Enum):
    """Hacia donde apunta una pista."""
    FALSA = "falsa"
    VERDADERA = "verdadera"
    NEUTRA = "neutra"       # no prueba nada ("es muy viral", "foto de archivo"): una pista enganosa


@dataclass(frozen=True)
class Pista:
    id: str
    zona: ZonaTarjeta
    titulo: str          # etiqueta corta: "Cuenta sospechosa"
    hallazgo: str        # lo que se descubre al investigar
    senal: Senal
    costo: int = 1       # energia

    def __post_init__(self) -> None:
        if not self.id or not self.titulo.strip() or not self.hallazgo.strip():
            raise ValueError(f"Pista incompleta: {self.id!r}")
        if not COSTO_MIN <= self.costo <= COSTO_MAX:
            raise ValueError(f"El costo de {self.id} debe estar entre {COSTO_MIN} y {COSTO_MAX}: {self.costo}")

    def to_dict(self) -> dict:
        return {"id": self.id, "zona": self.zona.value, "titulo": self.titulo, "hallazgo": self.hallazgo,
                "senal": self.senal.value, "costo": self.costo}

    @classmethod
    def from_dict(cls, d: dict) -> "Pista":
        return cls(d["id"], ZonaTarjeta(d["zona"]), d["titulo"], d["hallazgo"], Senal(d["senal"]),
                   int(d.get("costo", 1)))


def validar_pistas(pistas: Iterable[Pista]) -> tuple[Pista, ...]:
    """Ids unicos y una sola pista por zona de la tarjeta (cada zona clicable abre una pista)."""
    pistas = tuple(pistas)
    ids = [p.id for p in pistas]
    zonas = [p.zona for p in pistas]
    if len(set(ids)) != len(ids):
        raise ValueError("Hay pistas con id repetido")
    if len(set(zonas)) != len(zonas):
        raise ValueError("Hay dos pistas en la misma zona de la tarjeta")
    return pistas


@dataclass(frozen=True)
class VarianteTexto:
    """Texto de consecuencia que se usa cuando YA se descubrieron todas las pistas de `si`."""
    si: frozenset[str]
    texto: str

    def __post_init__(self) -> None:
        if not self.si:
            raise ValueError("Una variante necesita al menos una pista en `si`")
        if not self.texto.strip():
            raise ValueError("Una variante necesita texto")

    def to_dict(self) -> dict:
        return {"si": sorted(self.si), "texto": self.texto}

    @classmethod
    def from_dict(cls, d: dict) -> "VarianteTexto":
        return cls(frozenset(d["si"]), d["texto"])


def elegir_variante(variantes: Iterable[VarianteTexto], descubiertas: Iterable[str]) -> VarianteTexto | None:
    """La variante MAS ESPECIFICA aplicable (la que exige mas pistas, todas ya descubiertas); si
    empatan, la primera escrita. None si no aplica ninguna. Costo: O(variantes)."""
    descubiertas = set(descubiertas)
    mejor: VarianteTexto | None = None
    for v in variantes:
        if v.si <= descubiertas and (mejor is None or len(v.si) > len(mejor.si)):
            mejor = v
    return mejor


def texto_consecuencia(base: str, variantes: Iterable[VarianteTexto], descubiertas: list[Pista]) -> str:
    """Texto final de una decision: la variante que corresponde a lo investigado; si no hay, el
    texto base con una frase corta de las pistas revisadas; sin pistas, el texto base."""
    variante = elegir_variante(variantes, (p.id for p in descubiertas))
    if variante is not None:
        return variante.texto
    if not descubiertas:
        return base
    return f"{base} Habias revisado: {', '.join(p.titulo.lower() for p in descubiertas)}."


@dataclass(frozen=True)
class ResultadoInvestigacion:
    estado: str   # "nueva": se gasto energia | "repetida": ya estaba revelada | "sin_energia": no alcanza
    pista: Pista


@dataclass
class Investigacion:
    """Estado de la revision de UNA publicacion: energia disponible y pistas descubiertas."""
    pistas: tuple[Pista, ...]
    energia_max: int = ENERGIA_POR_NOTICIA
    energia: int = -1
    descubiertas: list[str] = field(default_factory=list)   # ids, en el orden en que se revisaron

    def __post_init__(self) -> None:
        validar_pistas(self.pistas)
        if self.energia < 0:
            self.energia = self.energia_max
        conocidas = {p.id for p in self.pistas}
        if not set(self.descubiertas) <= conocidas:
            raise ValueError("Hay pistas descubiertas que no existen en la noticia")

    def pista(self, id: str) -> Pista:
        for p in self.pistas:
            if p.id == id:
                return p
        raise KeyError(f"No existe la pista: {id}")

    def pista_en(self, zona: ZonaTarjeta) -> Pista | None:
        return next((p for p in self.pistas if p.zona is zona), None)

    def esta_descubierta(self, id: str) -> bool:
        return id in self.descubiertas

    def pistas_descubiertas(self) -> list[Pista]:
        return [self.pista(id) for id in self.descubiertas]

    def investigar(self, id: str) -> ResultadoInvestigacion:
        """Revisa una pista. Una ya revelada se relee sin costo; si la energia no alcanza no se
        cobra nada. O(pistas)."""
        pista = self.pista(id)
        if id in self.descubiertas:
            return ResultadoInvestigacion("repetida", pista)
        if pista.costo > self.energia:
            return ResultadoInvestigacion("sin_energia", pista)
        self.energia -= pista.costo
        self.descubiertas.append(id)
        return ResultadoInvestigacion("nueva", pista)

    def veredicto(self) -> str:
        """Lo que sugiere la evidencia reunida: "falsa", "verdadera" o "incierta" (sin pistas,
        solo neutras o empate)."""
        falsas = sum(p.senal is Senal.FALSA for p in self.pistas_descubiertas())
        verdaderas = sum(p.senal is Senal.VERDADERA for p in self.pistas_descubiertas())
        if falsas > verdaderas:
            return "falsa"
        if verdaderas > falsas:
            return "verdadera"
        return "incierta"

    def to_dict(self) -> dict:
        return {"energia_max": self.energia_max, "energia": self.energia, "descubiertas": list(self.descubiertas)}

    @classmethod
    def from_dict(cls, datos: dict, pistas: Iterable[Pista]) -> "Investigacion":
        """Las pistas vienen de la noticia (events.json); aqui solo se guarda el progreso."""
        return cls(tuple(pistas), int(datos["energia_max"]), int(datos["energia"]),
                   list(datos.get("descubiertas", [])))
