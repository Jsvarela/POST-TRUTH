"""Minijuego del Colegio, "Chat bajo presion": un chat donde atacan a una estudiante; el jugador responde con tiempo
limite por turno. La conversacion es un arbol de dialogo N-ario (structures/arbol_dialogo.py) con ramas de
desescalar, ignorar o amplificar; jugar es bajar de la raiz a una hoja por las respuestas elegidas."""
from __future__ import annotations

import json
from functools import lru_cache

from post_truth.config import RUTA_CHAT
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar
from post_truth.structures.arbol_dialogo import NodoDialogo

TECLAS = ("1", "2", "3")


@lru_cache(maxsize=1)
def datos() -> tuple[dict, NodoDialogo]:
    with RUTA_CHAT.open("r", encoding="utf-8") as f:
        d = json.load(f)
    return d, NodoDialogo.from_dict(d["arbol"])


@registrar
class Chat(Minijuego):
    id = "chat"
    nombre = "Chat bajo presion"
    ayuda = ("Atacan a Sofi en el chat del curso. Elige tu respuesta con 1, 2 o 3 antes de que se acabe el tiempo: "
             "calmar, ignorar o echarle lena. Lo que escribes cambia como sigue la conversacion.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.camino: list[int] = []      # opcion elegida en cada turno (el recorrido raiz -> hoja)
        self.tipos: list[str] = []       # desescalar | ignorar | amplificar | tarde
        self.t = 0.0

    @property
    def raiz(self) -> NodoDialogo:
        return datos()[1]

    @property
    def limite(self) -> float:
        return datos()[0]["segundos_por_turno"] * self.contexto.ritmo

    @property
    def nodo_actual(self) -> NodoDialogo | None:
        return self.raiz.seguir(self.camino)

    @property
    def historia(self) -> list[tuple[str, str, str]]:
        """(hablante, mensaje, lo que respondio el jugador) de los turnos ya jugados."""
        nodo, filas = self.raiz, []
        for i in self.camino:
            filas.append((nodo.hablante, nodo.texto, nodo.opciones[i].texto))
            nodo = nodo.opciones[i].hijo
        return filas

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        if self.t >= self.limite:   # nadie respondio: cuenta como ignorar y ademas pesa en el bienestar
            self._responder(next(i for i, o in enumerate(self.nodo_actual.opciones) if o.tipo == "ignorar"), "tarde")

    def accion(self, nombre: str) -> None:
        nodo = self.nodo_actual
        if nodo is not None and nombre in TECLAS and int(nombre) <= len(nodo.opciones):
            i = int(nombre) - 1
            self._responder(i, nodo.opciones[i].tipo)

    def _responder(self, i: int, tipo: str) -> None:
        self.camino.append(i)
        self.tipos.append(tipo)
        self.t = 0.0

    @property
    def terminado(self) -> bool:
        return self.nodo_actual is None

    def resultado(self) -> ResultadoMinijuego:
        efectos = datos()[0]["efectos"]
        total: dict[str, int] = {}
        for tipo in self.tipos:
            for clave in ([tipo] if tipo != "tarde" else ["ignorar", "tarde"]):
                for k, v in efectos[clave].items():
                    total[k] = total.get(k, 0) + v
        credibilidad = total.pop("credibilidad", 0)
        calma, lena = self.tipos.count("desescalar"), self.tipos.count("amplificar")
        if calma == len(self.tipos):
            texto = "Desescalaste todo el chat: Sofi tuvo apoyo y el ataque perdio fuerza."
        elif lena > calma:
            texto = "Le echaste lena al chat: el ataque crecio y Sofi quedo mas sola."
        else:
            texto = f"Calmaste {calma} de {len(self.tipos)} momentos del chat."
        return ResultadoMinijuego(Impact(**total), credibilidad, texto)

    def estado(self) -> dict:
        return {"camino": self.camino, "tipos": self.tipos, "t": self.t}

    def restaurar(self, estado: dict) -> None:
        self.camino, self.tipos, self.t = list(estado["camino"]), list(estado["tipos"]), float(estado["t"])
