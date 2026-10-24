"""Arbol de dialogo N-ario: cada nodo es lo que dice alguien y cada opcion de respuesta lleva a un hijo (o termina).

RECORRIDO al jugar: un camino de la raiz a una hoja guiado por las respuestas. Cada turno baja un nivel siguiendo la
opcion elegida, asi que jugar cuesta O(1) por turno y O(h) en total (h = profundidad); no se visitan las otras ramas.
Para analizar el arbol (cuantos finales hay, cual es el mejor camino) se usa DFS, O(n) en el numero de nodos:
DFS porque cada final es una hoja y hay que bajar hasta ella para conocer el valor del camino completo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Opcion:
    texto: str
    tipo: str                         # p. ej. desescalar | ignorar | amplificar, o lo que use cada dialogo
    hijo: NodoDialogo | None = None   # None: la conversacion termina aqui


@dataclass
class NodoDialogo:
    hablante: str
    texto: str
    opciones: list[Opcion] = field(default_factory=list)

    @property
    def es_hoja(self) -> bool:
        return all(o.hijo is None for o in self.opciones)

    @classmethod
    def from_dict(cls, d: dict) -> "NodoDialogo":
        """El JSON ya viene anidado como arbol: {"hablante", "texto", "opciones": [{"texto", "tipo", "sigue"}]}."""
        if not d.get("texto", "").strip():
            raise ValueError("Nodo de dialogo sin texto")
        opciones = [Opcion(o["texto"], o["tipo"], cls.from_dict(o["sigue"]) if o.get("sigue") else None)
                    for o in d.get("opciones", [])]
        return cls(d.get("hablante", ""), d["texto"], opciones)

    def seguir(self, camino: list[int]) -> NodoDialogo | None:
        """El nodo al que se llega eligiendo esas opciones (None si la conversacion ya termino)."""
        nodo: NodoDialogo | None = self
        for i in camino:
            if nodo is None:
                return None
            nodo = nodo.opciones[i].hijo
        return nodo

    def contar_finales(self) -> int:
        """DFS: cuantas formas distintas tiene de terminar la conversacion (opciones sin hijo)."""
        return sum(1 if o.hijo is None else o.hijo.contar_finales() for o in self.opciones)

    def profundidad(self) -> int:
        """Turnos del camino mas largo."""
        return 1 + max((o.hijo.profundidad() for o in self.opciones if o.hijo is not None), default=0)

    def mejor_camino(self, valor: Callable[[Opcion], float]) -> tuple[float, list[int]]:
        """DFS: el camino (indices de opcion) que maximiza la suma de `valor`."""
        mejor: tuple[float, list[int]] = (float("-inf"), [])
        for i, o in enumerate(self.opciones):
            resto, camino = o.hijo.mejor_camino(valor) if o.hijo is not None else (0.0, [])
            if valor(o) + resto > mejor[0]:
                mejor = (valor(o) + resto, [i] + camino)
        return mejor
