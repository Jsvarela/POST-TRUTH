"""Controlador de la eleccion del alcalde al final de la campana."""
import pygame

from post_truth.config import RUTA_INTRO
from post_truth.controllers.base_state import BaseState
from post_truth.models.intro import Intro
from post_truth.views.resultado_view import dibujar_resultado

DURACION_CONTEO = 1.5   # segundos en que crecen las barras


class ResultadoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.candidatos = list(Intro.cargar(RUTA_INTRO).candidatos)
        self.t = 0.0

    def al_entrar(self) -> None:
        self.t = 0.0
        self.resultado = self.app.partida.resultado_eleccion()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.app.partida = None
            self.app.estados.cambiar("menu")

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_resultado(pantalla, self.app.fuentes, self.app.temas.actual, self.resultado, self.candidatos,
                          self.app.partida.ciudad.score, min(1.0, self.t / DURACION_CONTEO))
