"""Controlador de la eleccion del alcalde al final de la campana."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import reparto
from post_truth.views.theme import NEGRO
from post_truth.views.resultado_view import dibujar_resultado

DURACION_CONTEO = 3.0   # segundos del conteo animado


class ResultadoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.candidatos = list(reparto.candidatos())
        self.t = 0.0

    NOMBRE = "resultado"

    def al_entrar(self) -> None:
        self.t, self.cubrir = 0.0, True
        self.resultado = self.app.partida.resultado_eleccion()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE or (self.t < DURACION_CONTEO and event.key == pygame.K_RETURN):
            self.t = DURACION_CONTEO   # saltar el conteo (accesibilidad)
        elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.app.salir_de_red()
            self.app.partida = None
            self.app.estados.cambiar("menu")

    def update(self, dt: float) -> None:
        self.cubrir = self.app.estados.estado("cinematica").si_toca(self.NOMBRE)   # L4: primero su cinematica
        if self.cubrir:
            return
        self.t += dt

    def draw(self, pantalla: pygame.Surface) -> None:
        if self.cubrir and self.app.partida is not None and self.app.partida.con_cinematicas:
            pantalla.fill(NEGRO)   # sin asomarse antes de la cinematica pendiente
            return
        s = self.app.partida
        nombre = (lambda j: f"{s.nombre(j.id)} ({j.personaje.rol.value})") if getattr(s, "en_red", False) else (
            lambda j: j.personaje.rol.value)
        jugadores = [(nombre(j), j.puntos, j.credibilidad) for j in s.jugadores]
        dibujar_resultado(pantalla, self.app.fuentes, self.app.temas.actual, self.resultado, self.candidatos,
                          s.ciudad.score, min(1.0, self.t / DURACION_CONTEO), jugadores)
