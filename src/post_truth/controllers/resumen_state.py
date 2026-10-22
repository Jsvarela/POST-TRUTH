"""Controlador del resumen del dia de campana."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.game_state import CityState
from post_truth.models import Impact
from post_truth.views.resumen_view import dibujar_resumen


class ResumenState(BaseState):
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.app.partida.empezar_siguiente_dia():
                self.app.estados.cambiar("mundo", fundido=True)
            else:
                self.app.estados.cambiar("resultado", fundido=True)

    def update(self, dt: float) -> None:
        pass

    def cambio(self) -> Impact:
        """Diferencia entre la ciudad de ahora y la del amanecer (mismos campos que Impact)."""
        antes = CityState.from_dict(self.app.partida.campana.ciudad_al_amanecer).to_dict()
        ahora = self.app.partida.ciudad.to_dict()
        return Impact(**{k: ahora[k] - antes[k] for k in ahora})

    def draw(self, pantalla: pygame.Surface) -> None:
        s = self.app.partida
        c = s.campana
        decisiones = [(s.arboles[i].event.title, accion) for i, accion in c.resueltas]
        dibujar_resumen(pantalla, self.app.fuentes, self.app.temas.actual, c.dia + 1, len(c.dias),
                        s.ciudad.as_display_rows(), self.cambio(), decisiones)
