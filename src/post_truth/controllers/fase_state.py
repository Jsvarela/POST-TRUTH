"""Transicion entre fases electorales: se muestra despues del resumen del dia cuando empieza una fase nueva."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import fases
from post_truth.views import sonido
from post_truth.views.fase_view import dibujar_fase


class FaseState(BaseState):
    def al_entrar(self) -> None:
        self.t = 0.0
        sonido.tocar("fase")   # aviso visual: esta misma pantalla

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.partida.anunciar_fase = False
            self.app.estados.cambiar("mundo", fundido=True)

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, pantalla: pygame.Surface) -> None:
        s = self.app.partida
        dibujar_fase(pantalla, self.app.fuentes, self.app.temas.actual, s.fase_campana + 1,
                     len(fases.reglas().fases), s.fase_actual, s.cambios_fase, self.t)
