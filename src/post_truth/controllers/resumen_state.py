"""Controlador del resumen del dia de campana."""
import pygame

from post_truth.config import px

from post_truth.controllers.base_state import BaseState
from post_truth.game_state import CityState
from post_truth.models import Impact
from post_truth.sesion import FIN, FIN_DIA
from post_truth.views.hud import DatosHud
from post_truth.views.resumen_view import dibujar_resumen


class ResumenState(BaseState):
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.en_red:   # el servidor sigue cuando todos lo pasan; update espera su foto
                self.app.partida.empezar_siguiente_dia()
            elif self.app.partida.empezar_siguiente_dia():
                self.app.estados.cambiar("fase" if self.app.partida.anunciar_fase else "mundo", fundido=True)
            else:
                self.app.estados.cambiar("resultado", fundido=True)

    @property
    def en_red(self) -> bool:
        return getattr(self.app.partida, "en_red", False)

    def update(self, dt: float) -> None:
        s = self.app.partida
        if self.en_red and s.fase != FIN_DIA:
            if s.fase == FIN:
                self.app.estados.cambiar("resultado", fundido=True)
            else:
                self.app.estados.cambiar("fase" if s.anunciar_fase else "mundo", fundido=True)

    def cambio(self) -> Impact:
        """Diferencia entre la ciudad de ahora y la del amanecer (mismos campos que Impact)."""
        antes = CityState.from_dict(self.app.partida.campana.ciudad_al_amanecer).to_dict()
        ahora = self.app.partida.ciudad.to_dict()
        return Impact(**{k: ahora[k] - antes[k] for k in ahora})

    def datos_hud(self) -> DatosHud:
        s = self.app.partida
        return DatosHud(s.ciudad.as_display_rows(), self._jugador().credibilidad, origen=id(s.ciudad))

    def _jugador(self):
        s = self.app.partida
        return s.jugador_actual if self.en_red else s.jugadores[0]   # en red, el de esta pantalla

    def draw(self, pantalla: pygame.Surface) -> None:
        s = self.app.partida
        c = s.campana
        j = self._jugador()   # shortcut: en el modo local con varios jugadores se resume solo al primero
        hoy = {s.arboles[i].event.event_id for i, _ in c.resueltas}
        por_evento = {h["evento"]: h["credibilidad"] for h in j.historial if h["evento"] in hoy}
        decisiones = [(s.arboles[i].event.title, accion, por_evento.get(s.arboles[i].event.event_id, 0))
                      for i, accion in c.resueltas]
        dibujar_resumen(pantalla, self.app.fuentes, self.app.temas.actual, c.dia + 1, len(c.dias),
                        s.ciudad.as_display_rows(), self.cambio(), decisiones, j.credibilidad,
                        sum(por_evento.values()))
        if self.en_red and s.esperando:
            listos = "Esperando a los demas jugadores..."
            img = self.app.fuentes.normal.render(listos, True, self.app.temas.actual.acento)
            pantalla.blit(img, img.get_rect(midbottom=(pantalla.get_width() // 2, pantalla.get_height() - px(40))))
