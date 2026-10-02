"""Modelo: pistas de una noticia, investigacion con energia y texto de consecuencia. Logica pura.

IDEA DE JUEGO
    La tarjeta de una publicacion tiene partes revisables (autor, fuente, fecha, imagen, texto,
    estadisticas). Cada una puede esconder una PISTA que apunta a que la noticia es falsa, a que
    es verdadera o que no prueba nada (neutra). Investigar una pista revela su hallazgo y gasta
    ENERGIA; hay mas pistas que energia, asi que el jugador debe elegir que revisar antes de
    decidir. Las pistas no cambian los puntajes: cambian lo que el jugador SABE y el texto de la
    consecuencia (decidir con o sin evidencia no se cuenta igual).

La energia es el unico costo de investigar: nada mas cambia en la ciudad al revisar o viajar, asi que
investigar no delata si una noticia es falsa.

EVIDENCIA POR ZONA
    Ademas de las pistas de la tarjeta, cada noticia puede dejar EVIDENCIA en lugares del mapa de la
    ciudad (un testigo, un documento, una grabacion). Llegar a ese lugar cuesta energia (la distancia
    del camino mas corto, ver structures/grafo_ciudad.py) y al llegar la evidencia se revela como una
    pista mas: entra en el mismo registro (`descubiertas`), en el veredicto y en el texto de la
    consecuencia. La energia es UNA sola para revisar la tarjeta y para viajar.

RESPALDO
    Verificar y Reportar no exigen ir a ningun lado: su resultado depende del respaldo reunido
    (`Investigacion.respaldo`): 0 nada, 1 solo pistas de la tarjeta, 2 evidencia de campo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

ENERGIA_POR_NOTICIA = 3     # puntos que se recargan al abrir cada publicacion: sirven para revisar la tarjeta Y para viajar
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


class TipoEvidencia(Enum):
    TESTIGO = "testigo"
    DOCUMENTO = "documento"
    GRABACION = "grabacion"


@dataclass(frozen=True)
class Evidencia:
    """Evidencia de una noticia guardada en una zona del mapa. No tiene costo propio: se paga el viaje."""
    id: str
    lugar: str           # id de la zona de la ciudad donde esta (structures/grafo_ciudad.py)
    tipo: TipoEvidencia
    titulo: str          # "La directora del colegio"
    hallazgo: str        # lo que se descubre al llegar
    senal: Senal

    costo = 0  # misma interfaz que Pista; el costo es el del viaje

    def __post_init__(self) -> None:
        if not self.id or not self.lugar or not self.titulo.strip() or not self.hallazgo.strip():
            raise ValueError(f"Evidencia incompleta: {self.id!r}")

    def to_dict(self) -> dict:
        return {"id": self.id, "lugar": self.lugar, "tipo": self.tipo.value, "titulo": self.titulo,
                "hallazgo": self.hallazgo, "senal": self.senal.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Evidencia":
        return cls(d["id"], d["lugar"], TipoEvidencia(d["tipo"]), d["titulo"], d["hallazgo"], Senal(d["senal"]))


Hallazgo = Pista | Evidencia   # lo que se puede descubrir de una noticia


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
    """La variante MAS ESPECIFICA aplicable (la que exige mas pistas, todas ya descubiertas); si
    empatan, la primera escrita. None si no aplica ninguna. Costo: O(variantes)."""
    descubiertas = set(descubiertas)
    mejor: VarianteTexto | None = None
    for v in variantes:
        if v.si <= descubiertas and (mejor is None or len(v.si) > len(mejor.si)):
            mejor = v
    return mejor


def texto_consecuencia(base: str, variantes: Iterable[VarianteTexto], descubiertas: list[Hallazgo]) -> str:
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
    descubiertas: list[str] = field(default_factory=list)   # ids (pistas y evidencias), en el orden en que se hallaron
    evidencias: tuple[Evidencia, ...] = ()                  # lo que hay en el mapa de la ciudad
    viaje_gastado: int = 0                                  # energia gastada en viajes (el resto, en pistas)

    def __post_init__(self) -> None:
        validar_pistas(self.pistas)
        validar_evidencias(self.evidencias)
        if self.energia < 0:
            self.energia = self.energia_max
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
        """Todo lo descubierto (pistas de la tarjeta Y evidencias del mapa), en orden de hallazgo."""
        return [self.hallazgo(id) for id in self.descubiertas]

    # --- evidencia en el mapa ------------------------------------------------------------
    def evidencia_en(self, lugar: str) -> Evidencia | None:
        return next((e for e in self.evidencias if e.lugar == lugar), None)

    def lugares_pendientes(self) -> set[str]:
        """Zonas del mapa con evidencia de esta noticia que aun no se ha descubierto."""
        return {e.lugar for e in self.evidencias if e.id not in self.descubiertas}

    def lugares_revisados(self) -> set[str]:
        return {e.lugar for e in self.evidencias if e.id in self.descubiertas}

    def revelar_evidencia(self, lugar: str) -> Evidencia | None:
        """Al llegar a una zona: revela su evidencia si la hay y es nueva. No cuesta (ya se pago el
        viaje). Devuelve la evidencia recien descubierta, o None."""
        e = self.evidencia_en(lugar)
        if e is None or e.id in self.descubiertas:
            return None
        self.descubiertas.append(e.id)
        return e

    def viajar(self, costo: int) -> bool:
        """Gasta `costo` de energia en un viaje. False (y no cobra nada) si no alcanza. O(1)."""
        if costo < 0:
            raise ValueError("El costo de un viaje no puede ser negativo")
        if costo > self.energia:
            return False
        self.energia -= costo
        self.viaje_gastado += costo
        return True

    def respaldo(self, accion: str) -> int:
        """Que tan respaldada esta una accion con lo descubierto: 0 nada, 1 solo pistas de la tarjeta,
        2 evidencia de campo (testigo, documento o grabacion del mapa).
        "reportar" cuenta lo que apunta a FALSA (es lo que justifica un reporte); "verificar" cuenta
        todo lo que no es neutro (la verificacion se apoya en material concreto, sea a favor o en contra).
        """
        def apoya(h: Hallazgo) -> bool:
            return h.senal is Senal.FALSA if accion == "reportar" else h.senal is not Senal.NEUTRA
        hallazgos = self.pistas_descubiertas()
        if any(isinstance(h, Evidencia) and apoya(h) for h in hallazgos):
            return 2
        if any(isinstance(h, Pista) and apoya(h) for h in hallazgos):
            return 1
        return 0

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
        return {"energia_max": self.energia_max, "energia": self.energia, "descubiertas": list(self.descubiertas),
                "viaje_gastado": self.viaje_gastado}

    @classmethod
    def from_dict(cls, datos: dict, pistas: Iterable[Pista], evidencias: Iterable[Evidencia] = ()) -> "Investigacion":
        """Las pistas y evidencias vienen de la noticia (events.json); aqui solo se guarda el progreso."""
        return cls(tuple(pistas), int(datos["energia_max"]), int(datos["energia"]),
                   list(datos.get("descubiertas", [])), tuple(evidencias), int(datos.get("viaje_gastado", 0)))
