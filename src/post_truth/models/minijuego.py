"""Minijuegos de los lugares: interfaz comun, registro y un minijuego de prueba. Logica pura y serializable.

Cada minijuego se inicia con el contexto del lugar y del jugador, avanza con `update(dt)`, recibe acciones
(`accion("1")`) y al terminar da un `ResultadoMinijuego`: un Impacto para la ciudad y un cambio de credibilidad.
Los reales (chat de ciberacoso, mitin, rueda de prensa, persuasion) llegan en R5-R8 con esta misma interfaz.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
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

    def __init__(self, contexto: ContextoMinijuego) -> None:
        self.contexto = contexto

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


# --- minijuego de prueba: hasta que cada lugar tenga el suyo (R5-R8) ---------------------------------------
MENSAJES_ENSAYO = (
    ("Un vecino reenvia: 'Manana cortan el agua en todo el barrio'.",
     ("Le pregunto de donde salio", "Lo reenvio al grupo por si acaso")),
    ("Alguien escribe: 'Ese candidato es un ladron, todos lo saben'.",
     ("Pido pruebas con calma", "Le respondo con otro insulto")),
    ("Llega una foto 'de hoy' de la plaza llena de basura.",
     ("Reviso si la foto es vieja", "La comparto indignado")),
    ("Una cuenta nueva ofrece 'la encuesta real' de la eleccion.",
     ("Busco quien hizo la encuesta", "La publico en mi muro")),
)
SEGUNDOS_POR_MENSAJE = 7.0


@registrar
class Ensayo(Minijuego):
    """Tres mensajes del chat del lugar: responder con calma (1) o reaccionar sin pensar (2) antes del tiempo."""
    id = "ensayo"
    nombre = "Ensayo"
    ayuda = "Responde cada mensaje con 1 (con calma) o 2 (sin pensar) antes de que se acabe el tiempo."

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        inicio = contexto.dia % len(MENSAJES_ENSAYO)
        self.mensajes = [(inicio + k) % len(MENSAJES_ENSAYO) for k in range(3)]
        self.respuestas: list[str] = []   # "bien", "mal" o "tarde"
        self.t = 0.0

    @property
    def limite(self) -> float:
        return SEGUNDOS_POR_MENSAJE * (1.5 if self.contexto.extendido else 1.0)

    @property
    def mensaje_actual(self) -> tuple[str, tuple[str, str]] | None:
        return None if self.terminado else MENSAJES_ENSAYO[self.mensajes[len(self.respuestas)]]

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        if self.t >= self.limite:
            self._responder("tarde")

    def accion(self, nombre: str) -> None:
        if not self.terminado and nombre in ("1", "2"):
            self._responder("bien" if nombre == "1" else "mal")

    def _responder(self, como: str) -> None:
        self.respuestas.append(como)
        self.t = 0.0

    @property
    def terminado(self) -> bool:
        return len(self.respuestas) >= len(self.mensajes)

    def resultado(self) -> ResultadoMinijuego:
        bien, mal = self.respuestas.count("bien"), self.respuestas.count("mal")
        impacto = Impact(coexistence=2 * bien - 2 * mal, misinformation=2 * mal - bien, score=bien - mal)
        texto = f"Respondiste con calma {bien} de {len(self.mensajes)} mensajes."
        return ResultadoMinijuego(impacto, 2 * bien - 3 * mal, texto)

    def estado(self) -> dict:
        return {"mensajes": self.mensajes, "respuestas": self.respuestas, "t": self.t}

    def restaurar(self, estado: dict) -> None:
        self.mensajes, self.respuestas, self.t = list(estado["mensajes"]), list(estado["respuestas"]), float(estado["t"])


from post_truth.models import chat, mitin  # noqa: E402,F401  (al importarse registran sus minijuegos)
