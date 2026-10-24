"""Pantalla que aloja cualquier minijuego de un lugar: pasa el teclado al modelo y aplica su resultado."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.views.hud import DatosHud
from post_truth.views.minijuego_view import dibujar_minijuego

TECLAS = {pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3", pygame.K_4: "4"}


class MinijuegoState(BaseState):
    def al_entrar(self) -> None:
        self.minijuego = self.app.partida.minijuego   # lo creo el mundo con sesion.iniciar_minijuego
        self.resultado = None
        self.pausado = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.resultado is not None:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.app.estados.cambiar("mundo", fundido=True)
        elif event.key == pygame.K_p:
            self.pausado = not self.pausado   # accesibilidad: el reloj del minijuego se detiene
        elif not self.pausado and event.key in TECLAS:
            self.minijuego.accion(TECLAS[event.key])

    def update(self, dt: float) -> None:
        if self.resultado is not None or self.pausado:
            return
        self.minijuego.update(dt)
        self.app.partida.transcurrir(dt)   # jugar cuesta tiempo del dia (la pausa lo detiene todo)
        if self.minijuego.terminado:
            self.resultado = self.app.partida.terminar_minijuego()

    def datos_hud(self) -> DatosHud:
        s = self.app.partida
        return DatosHud(s.ciudad.as_display_rows(), s.jugador(self.minijuego.contexto.jugador).credibilidad,
                        origen=id(s.ciudad))

    def draw(self, pantalla: pygame.Surface) -> None:
        s = self.app.partida
        dibujar_minijuego(pantalla, self.app.fuentes, self.app.temas.actual, self.minijuego, s.ciudad.as_display_rows(),
                          s.jugador(self.minijuego.contexto.jugador).credibilidad, self.resultado, self.pausado)
