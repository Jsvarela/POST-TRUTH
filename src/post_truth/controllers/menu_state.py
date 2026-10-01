"""Controlador del menu."""
import pygame
from post_truth.controllers.base_state import BaseState
from post_truth.views.menu_view import dibujar_menu


class MenuState(BaseState):
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Menu -> Intro -> Seleccion la primera vez; despues va directo a la seleccion
                self.app.estados.cambiar("seleccion" if self.app.intro_vista else "intro")
            elif event.key == pygame.K_i:
                self.app.estados.cambiar("intro")   # volver a ver la introduccion
            elif event.key == pygame.K_t:
                self.app.temas.siguiente()
            elif event.key == pygame.K_ESCAPE:
                self.app.corriendo = False

    def update(self, dt: float) -> None:
        pass

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_menu(pantalla, self.app.fuente, self.app.temas.actual)
