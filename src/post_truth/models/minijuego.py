"""Minijuegos de los lugares: interfaz comun, registro y un minijuego de prueba. Logica pura y serializable.

Cada minijuego se inicia con el contexto del lugar y del jugador, avanza con `update(dt)`, recibe acciones
(`accion("1")`) y al terminar da un `ResultadoMinijuego`: un Impacto para la ciudad y un cambio de credibilidad.
Los reales (chat de ciberacoso, mitin, rueda de prensa, persuasion) llegan en R5-R8 con esta misma interfaz.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path

from post_truth.models.dominio import Impact


@dataclass(frozen=True)
class ContextoMinijuego:
    lugar: str
    jugador: str
    rol: str
    credibilidad: int
    dia: int
    extendido: bool = False   # accesibilidad: mas tiempo (y sin ritmo en el mitin)
    evidencias: int = 0       # evidencia que el jugador ya reunio (el mitin la usa)
    crisis: bool = False      # el lugar esta en crisis (R9): menos tiempo
    municion: dict = field(default_factory=dict)   # pruebas reunidas por tipo: pista, evidencia, testimonio (rueda)
    jugadores: int = 1        # L6: en multijugador el minijuego es mas grande y mas dificil

    @property
    def extra(self) -> int:
        """Cuantos jugadores hay de mas (0 en el modo individual)."""
        return max(0, self.jugadores - 1)

    @property
    def ritmo(self) -> float:
        """Multiplica los tiempos: mas con tiempo extendido; menos si el lugar esta en crisis o hay mas jugadores."""
        return (1.5 if self.extendido else 1.0) * (0.8 if self.crisis else 1.0) * (1 - 0.1 * min(3, self.extra))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResultadoMinijuego:
    impacto: Impact
    credibilidad: int
    texto: str
    rumor: bool = False       # el resultado deja un rumor corriendo en la red

    def to_dict(self) -> dict:
        return {"impacto": asdict(self.impacto), "credibilidad": self.credibilidad, "texto": self.texto,
                "rumor": self.rumor}


class Minijuego(ABC):
    id = ""
    nombre = ""
    ayuda = ""   # que hacer y con que teclas: se muestra en pantalla
    simbolismo = ""   # que representa sobre el uso de las redes: se lee antes de jugar
    pasos_tutorial: tuple[str, ...] = ()   # subtitulos de "Como se juega" (models/tutorial.py); vacio: sin tutorial

    def __init__(self, contexto: ContextoMinijuego) -> None:
        self.contexto = contexto
        self.ecos: list[str] = []   # "acierto" / "error" desde el ultimo cuadro: la pantalla los hace sonar (no se guarda)

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def accion(self, nombre: str) -> None: ...

    @property
    @abstractmethod
    def terminado(self) -> bool: ...

    @abstractmethod
    def resultado(self) -> ResultadoMinijuego: ...

    @abstractmethod
    def estado(self) -> dict:
        """Lo propio de cada minijuego (para serializar)."""

    @abstractmethod
    def restaurar(self, estado: dict) -> None: ...

    def demo(self) -> list[str]:
        """Lo que haria ahora quien sabe jugar (acciones para `accion`): la demostracion de "Como se juega" y los
        bots. Por defecto nada: el minijuego termina solo con el tiempo."""
        return []

    def jugar_solo(self, dt: float = 0.1, maximo: float = 600.0) -> None:
        """Hasta terminar, con la demostracion (pruebas y bots)."""
        t = 0.0
        while not self.terminado and t < maximo:
            for a in self.demo():
                self.accion(a)
            self.update(dt)
            t += dt

    def to_dict(self) -> dict:
        return {"id": self.id, "contexto": self.contexto.to_dict(), "estado": self.estado()}


REGISTRO: dict[str, type[Minijuego]] = {}


def registrar(clase: type[Minijuego]) -> type[Minijuego]:
    REGISTRO[clase.id] = clase
    return clase


def crear(id: str, contexto: ContextoMinijuego) -> Minijuego:
    return REGISTRO[id](contexto)


def desde_dict(d: dict) -> Minijuego:
    m = crear(d["id"], ContextoMinijuego(**d["contexto"]))
    m.restaurar(d["estado"])
    return m


def cargar_lugares(ruta: str | Path) -> dict[str, str]:
    """data/minijuegos.json: que minijuego tiene cada lugar. Falla si nombra uno que no existe."""
    with Path(ruta).open("r", encoding="utf-8") as f:
        lugares = json.load(f)
    desconocidos = set(lugares.values()) - set(REGISTRO)
    if desconocidos:
        raise ValueError(f"Minijuegos desconocidos: {sorted(desconocidos)}")
    return lugares


from post_truth.models import boca_en_boca, chat, mitin, rueda_prensa  # noqa: E402,F401  (al importarse registran sus minijuegos)
