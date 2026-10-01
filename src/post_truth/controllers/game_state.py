"""Controlador del juego: teclas -> nodo del DecisionTree -> CityState.

Reutiliza el modelo de la entrega 1 (no se duplica): `DecisionTree` carga
data/events.json, `CityState` guarda los indicadores e `Impact` son los deltas.
"""
from pathlib import Path

import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.views.game_view import dibujar_juego

EVENTS_PATH = Path(__file__).resolve().parents[3] / "data" / "events.json"
TECLAS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]


class GameState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.ciudad = CityState()
        self.arboles: list[DecisionTree] = load_trees(EVENTS_PATH)
        self.indice = 0
        self.ultimo: DecisionNode | None = None  # ultima decision tomada (feedback)

    @property
    def arbol(self) -> DecisionTree:
        return self.arboles[self.indice]

    def opciones(self) -> list[DecisionNode]:
        # Las acciones varian por evento (p. ej. "Buscar video completo"), por eso
        # los botones salen de los hijos de la raiz y no de un enum fijo.
        return self.arbol.root.children[: len(TECLAS)]

    def decidir(self, nodo: DecisionNode) -> None:
        self.ciudad.apply(nodo.impact)
        self.ultimo = nodo
        self.indice = (self.indice + 1) % len(self.arboles)  # siguiente publicacion

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.estados.cambiar("menu")
        elif event.key in TECLAS:
            i = TECLAS.index(event.key)
            if i < len(self.opciones()):
                self.decidir(self.opciones()[i])

    def update(self, dt: float) -> None:
        pass  # aqui iran temporizadores basados en dt

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_juego(pantalla, self.app.fuente, self.app.temas.actual,
                      self.ciudad.as_display_rows(),
                      self.arbol.event.title, self.arbol.event.content,
                      [n.label for n in self.opciones()],
                      self.ultimo.description if self.ultimo else "")
