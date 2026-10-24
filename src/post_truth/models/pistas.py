"""Modelo: pistas de una noticia, investigacion y texto de consecuencia."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

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
    NEUTRA = "neutra"


@dataclass(frozen=True)
class Pista:
    id: str
    zona: ZonaTarjeta
    titulo: str
    hallazgo: str
    senal: Senal

    def __post_init__(self) -> None:
        if not self.id or not self.titulo.strip() or not self.hallazgo.strip():
            raise ValueError(f"Pista incompleta: {self.id!r}")

    def to_dict(self) -> dict:
        return {"id": self.id, "zona": self.zona.value, "titulo": self.titulo, "hallazgo": self.hallazgo,
                "senal": self.senal.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Pista":
        return cls(d["id"], ZonaTarjeta(d["zona"]), d["titulo"], d["hallazgo"], Senal(d["senal"]))


def validar_pistas(pistas: Iterable[Pista]) -> tuple[Pista, ...]:
    """Ids unicos y una sola pista por zona de la tarjeta."""
    pistas = tuple(pistas)
    ids = [p.id for p in pistas]
    zonas = [p.zona for p in pistas]
    if len(set(ids)) != len(ids):
        raise ValueError("Hay pistas con id repetido")
    if len(set(zonas)) != len(zonas):
        raise ValueError("Hay dos pistas en la misma zona de la tarjeta")
    return pistas


class TipoEvidencia(Enum):
    TESTIGO = "testigo"
    DOCUMENTO = "documento"
    GRABACION = "grabacion"


@dataclass(frozen=True)
class Evidencia:
    """Evidencia de una noticia guardada en una zona del mapa: se revela al llegar a esa zona."""
    id: str
    lugar: str
    tipo: TipoEvidencia
    titulo: str
    hallazgo: str
    senal: Senal

    def __post_init__(self) -> None:
        if not self.id or not self.lugar or not self.titulo.strip() or not self.hallazgo.strip():
            raise ValueError(f"Evidencia incompleta: {self.id!r}")

    def to_dict(self) -> dict:
        return {"id": self.id, "lugar": self.lugar, "tipo": self.tipo.value, "titulo": self.titulo,
                "hallazgo": self.hallazgo, "senal": self.senal.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Evidencia":
        return cls(d["id"], d["lugar"], TipoEvidencia(d["tipo"]), d["titulo"], d["hallazgo"], Senal(d["senal"]))


Hallazgo = Pista | Evidencia


def validar_evidencias(evidencias: Iterable[Evidencia]) -> tuple[Evidencia, ...]:
    """Ids unicos y a lo sumo una evidencia por zona del mapa para cada noticia."""
    evidencias = tuple(evidencias)
    if len({e.id for e in evidencias}) != len(evidencias):
        raise ValueError("Hay evidencias con id repetido")
    if len({e.lugar for e in evidencias}) != len(evidencias):
        raise ValueError("Hay dos evidencias en la misma zona")
    return evidencias


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
    """La variante mas especifica aplicable."""
    descubiertas = set(descubiertas)
    mejor: VarianteTexto | None = None
    for v in variantes:
        if v.si <= descubiertas and (mejor is None or len(v.si) > len(mejor.si)):
            mejor = v
    return mejor


def texto_consecuencia(base: str, variantes: Iterable[VarianteTexto], descubiertas: list[Hallazgo]) -> str:
    """Texto final de una decision: la variante que corresponde a lo investigado."""
    variante = elegir_variante(variantes, (p.id for p in descubiertas))
    if variante is not None:
        return variante.texto
    if not descubiertas:
        return base
    return f"{base} Habias revisado: {', '.join(p.titulo.lower() for p in descubiertas)}."


@dataclass(frozen=True)
class ResultadoInvestigacion:
    estado: str
    pista: Pista


CALIDAD_BUENA = 2   # hallazgos que apuntan a la verdad para que una conclusion cuente como bien respaldada


@dataclass
class Investigacion:
    """Estado de la revision de UNA publicacion: pistas y evidencias descubiertas, testimonios y la conclusion."""
    pistas: tuple[Pista, ...]
    descubiertas: list[str] = field(default_factory=list)
    evidencias: tuple[Evidencia, ...] = ()
    testimonios: dict[str, str] = field(default_factory=dict)   # testigo -> fiabilidad (ya conto su version)
    conclusion: str | None = None      # falsa | verdadera | no_concluyente
    acierto: bool | None = None        # None: sin concluir o no concluyente
    calidad_conclusion: int = 0

    def __post_init__(self) -> None:
        validar_pistas(self.pistas)
        validar_evidencias(self.evidencias)
        ids = [p.id for p in self.pistas] + [e.id for e in self.evidencias]
        if len(set(ids)) != len(ids):
            raise ValueError("Una pista y una evidencia no pueden compartir id")
        if not set(self.descubiertas) <= set(ids):
            raise ValueError("Hay hallazgos descubiertos que no existen en la noticia")

    def pista(self, id: str) -> Pista:
        for p in self.pistas:
            if p.id == id:
                return p
        raise KeyError(f"No existe la pista: {id}")

    def pista_en(self, zona: ZonaTarjeta) -> Pista | None:
        return next((p for p in self.pistas if p.zona is zona), None)

    def esta_descubierta(self, id: str) -> bool:
        return id in self.descubiertas

    def hallazgo(self, id: str) -> Hallazgo:
        """La pista o la evidencia con ese id."""
        for h in (*self.pistas, *self.evidencias):
            if h.id == id:
                return h
        raise KeyError(f"No existe el hallazgo: {id}")

    def pistas_descubiertas(self) -> list[Hallazgo]:
        """Todo lo descubierto, en orden de hallazgo."""
        return [self.hallazgo(id) for id in self.descubiertas]

    def evidencia_en(self, lugar: str) -> Evidencia | None:
        return next((e for e in self.evidencias if e.lugar == lugar), None)

    def lugares_pendientes(self) -> set[str]:
        """Zonas del mapa con evidencia de esta noticia que aun no se ha descubierto."""
        return {e.lugar for e in self.evidencias if e.id not in self.descubiertas}

    def lugares_revisados(self) -> set[str]:
        return {e.lugar for e in self.evidencias if e.id in self.descubiertas}

    def revelar_evidencia(self, lugar: str) -> Evidencia | None:
        """Al llegar a una zona: revela su evidencia si la hay y es nueva."""
        e = self.evidencia_en(lugar)
        if e is None or e.id in self.descubiertas:
            return None
        self.descubiertas.append(e.id)
        return e

    def respaldo(self, accion: str) -> int:
        """Que tan respaldada esta una accion con lo descubierto. La conclusion de la ventana de investigacion
        manda: equivocarse la deja sin respaldo; acertar la sube (mas si la evidencia era buena), y para reportar
        solo cuenta si se concluyo que es falsa."""
        def apoya(h: Hallazgo) -> bool:
            return h.senal is Senal.FALSA if accion == "reportar" else h.senal is not Senal.NEUTRA
        hallazgos = self.pistas_descubiertas()
        if any(isinstance(h, Evidencia) and apoya(h) for h in hallazgos):
            base = 2
        elif any(isinstance(h, Pista) and apoya(h) for h in hallazgos):
            base = 1
        else:
            base = 0
        if self.acierto is False:
            return 0
        if self.acierto and (accion != "reportar" or self.conclusion == "falsa"):
            return max(base, 2 if self.calidad_conclusion >= CALIDAD_BUENA else 1)
        return base

    @property
    def como_concluyo(self) -> str:
        """'' sin concluir; si no: buena | a_ciegas | error | no_concluyente."""
        if self.conclusion is None or self.conclusion == "no_concluyente":
            return self.conclusion or ""
        if not self.acierto:
            return "error"
        return "buena" if self.calidad_conclusion >= CALIDAD_BUENA else "a_ciegas"

    def calidad(self, es_falsa: bool) -> int:
        """Cuanto de lo reunido apunta a la verdad: senales y evidencias que coinciden, y testigos fiables
        (los de otras zonas ya cuentan como evidencia)."""
        verdad = Senal.FALSA if es_falsa else Senal.VERDADERA
        return (sum(h.senal is verdad for h in self.pistas_descubiertas())
                + sum(f == "veraz" for f in self.testimonios.values()))

    def investigar(self, id: str) -> ResultadoInvestigacion:
        """Revisa una pista."""
        pista = self.pista(id)
        if id in self.descubiertas:
            return ResultadoInvestigacion("repetida", pista)
        self.descubiertas.append(id)
        return ResultadoInvestigacion("nueva", pista)

    def veredicto(self) -> str:
        """Lo que sugiere la evidencia reunida: "falsa", "verdadera" o "incierta"."""
        falsas = sum(p.senal is Senal.FALSA for p in self.pistas_descubiertas())
        verdaderas = sum(p.senal is Senal.VERDADERA for p in self.pistas_descubiertas())
        if falsas > verdaderas:
            return "falsa"
        if verdaderas > falsas:
            return "verdadera"
        return "incierta"

    def to_dict(self) -> dict:
        return {"descubiertas": list(self.descubiertas), "testimonios": dict(self.testimonios),
                "conclusion": self.conclusion, "acierto": self.acierto, "calidad_conclusion": self.calidad_conclusion}

    @classmethod
    def from_dict(cls, datos: dict, pistas: Iterable[Pista], evidencias: Iterable[Evidencia] = ()) -> "Investigacion":
        """Las pistas y evidencias vienen de la noticia."""
        return cls(tuple(pistas), list(datos.get("descubiertas", [])), tuple(evidencias),
                   dict(datos.get("testimonios", {})), datos.get("conclusion"), datos.get("acierto"),
                   int(datos.get("calidad_conclusion", 0)))
