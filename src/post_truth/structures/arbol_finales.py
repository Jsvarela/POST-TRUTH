"""Arbol de decision de los finales (L4): elige como termina la historia a partir del estado final de la partida.

Es un arbol binario: cada nodo interno pregunta una condicion ("desinformacion<50", "credibilidad>=55", con la misma
sintaxis que las cinematicas) y cada hoja es un final. Se recorre de la raiz a una hoja siguiendo "si" o "no" en
cada nodo: O(altura), sin probar todas las combinaciones. Los datos estan en data/historia.json ("finales").
"""
from __future__ import annotations

from dataclasses import dataclass

from post_truth.models.cinematica import cumple


@dataclass(frozen=True)
class NodoFinal:
    pregunta: str = ""                    # vacia en las hojas
    si: "NodoFinal | None" = None
    no: "NodoFinal | None" = None
    final: str = ""                       # solo en las hojas: id de la cinematica del final

    @property
    def es_hoja(self) -> bool:
        return self.si is None and self.no is None

    @classmethod
    def from_dict(cls, d: dict | str) -> "NodoFinal":
        if isinstance(d, str):
            return cls(final=d)
        if not d.get("pregunta") or "si" not in d or "no" not in d:
            raise ValueError(f"Nodo de final incompleto: {d}")
        return cls(d["pregunta"], cls.from_dict(d["si"]), cls.from_dict(d["no"]))

    def elegir(self, ctx: dict) -> str:
        """Baja por el arbol respondiendo cada pregunta con el estado de la partida."""
        nodo = self
        while not nodo.es_hoja:
            nodo = nodo.si if cumple(nodo.pregunta, ctx) else nodo.no
        return nodo.final

    def hojas(self) -> list[str]:
        """DFS: todos los finales posibles (para validar los datos y sustentar)."""
        return [self.final] if self.es_hoja else self.si.hojas() + self.no.hojas()
