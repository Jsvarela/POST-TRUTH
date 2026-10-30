"""Pantalla que aloja cualquier minijuego de un lugar: pasa el teclado al modelo y aplica su resultado."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import guia
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views import hud
from post_truth.views.hud import DatosHud
from post_truth.views.minijuego_view import dibujar_minijuego

TECLAS = {pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3", pygame.K_4: "4", pygame.K_SPACE: "espacio",
          pygame.K_LEFT: "izq", pygame.K_a: "izq", pygame.K_RIGHT: "der", pygame.K_d: "der",
          pygame.K_UP: "arriba", pygame.K_w: "arriba", pygame.K_DOWN: "abajo", pygame.K_s: "abajo", pygame.K_e: "hablar"}


class MinijuegoState(BaseState):
    def al_entrar(self) -> None:
        self.minijuego = self.app.partida.minijuego   # lo creo el mundo con sesion.iniciar_minijuego
        self.resultado = None
        self.pausado = False
        m = guia.mensaje(f"minijuego:{self.minijuego.id}", self.app.guias_vistas, self.app.guias)
        self.toast = None if m is None else Anuncio(m[0], m[1], "info", grande=False, duracion=5.0)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP and event.key in TECLAS and self.resultado is None:
            self.minijuego.accion("-" + TECLAS[event.key])   # soltar: los que se mantienen (moverse, E, girar)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.resultado is not None:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.app.estados.cambiar("mundo", fundido=True)
        elif event.key == pygame.K_p:
            self.pausado = not self.pausado   # accesibilidad: el reloj del minijuego se detiene
        elif not self.pausado and event.key in TECLAS:
            self.minijuego.accion(TECLAS[event.key])
            self._sonar()

    def update(self, dt: float) -> None:
        if self.toast is not None:
            self.toast.avanzar(dt)
            self.toast = None if self.toast.terminado else self.toast
        if self.resultado is not None or self.pausado:
            return
        self.minijuego.update(dt)
        self.app.partida.transcurrir(dt)   # jugar cuesta tiempo del dia (la pausa lo detiene todo)
        self._sonar()
        if self.minijuego.terminado:
            self.resultado = self.app.partida.terminar_minijuego()
            sonido.tocar("acierto" if self.resultado.credibilidad >= 0 else "error")

    def _sonar(self) -> None:
        """Lo que acerto o fallo el jugador desde el ultimo cuadro (cada uno tiene ademas su aviso en pantalla)."""
        for eco in self.minijuego.ecos:
            sonido.tocar(eco)
        self.minijuego.ecos.clear()

    def datos_hud(self) -> DatosHud:
        s = self.app.partida
        return hud.minimo(s, s.jugador(self.minijuego.contexto.jugador).credibilidad, "barra")

    def draw(self, pantalla: pygame.Surface) -> None:
        s = self.app.partida
        dibujar_minijuego(pantalla, self.app.fuentes, self.app.temas.actual, self.minijuego, s.ciudad.as_display_rows(),
                          s.jugador(self.minijuego.contexto.jugador).credibilidad, self.resultado, self.pausado)
        if self.toast is not None:
            dibujar_anuncio(pantalla, self.app.fuentes, self.app.temas.actual, self.toast)
