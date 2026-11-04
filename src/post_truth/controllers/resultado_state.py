"""Controlador de la eleccion del alcalde al final de la campana."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import reparto
from post_truth.views.theme import NEGRO
from post_truth.views.final_view import dibujar_dia, dibujar_votos
from post_truth.views.resultado_view import dibujar_resultado

DURACION_CONTEO = 3.0   # segundos del conteo animado


class ResultadoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.candidatos = list(reparto.candidatos())
        self.t = 0.0

    NOMBRE = "resultado"

    def al_entrar(self) -> None:
        self.t, self.cubrir, self.pagina = 0.0, True, 0   # 0 el conteo; 1..N un dia cada una; N+1 la grafica
        self.resultado = self.app.partida.resultado_eleccion()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE or (self.t < DURACION_CONTEO and event.key == pygame.K_RETURN):
            self.t = DURACION_CONTEO   # saltar el conteo (accesibilidad)
        elif event.key in (pygame.K_RETURN, pygame.K_RIGHT, pygame.K_d) and self.pagina < self.paginas:
            self.pagina += 1   # las diapositivas del final
        elif event.key in (pygame.K_LEFT, pygame.K_a) and self.pagina > 1:
            self.pagina -= 1
        elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.app.salir_de_red()
            self.app.partida = None
            self.app.estados.cambiar("menu")

    @property
    def paginas(self) -> int:
        """Cuantas diapositivas hay despues del conteo (un dia cada una y la grafica); 0 sin bitacora."""
        b = self.app.partida.bitacora
        return len(b) + 1 if b else 0

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
        if 1 <= self.pagina <= len(s.bitacora):
            dibujar_dia(pantalla, self.app.fuentes, self.app.temas.actual, s.bitacora[self.pagina - 1], self.candidatos,
                        self.pagina - 1, self.paginas)
            return
        if self.pagina > len(s.bitacora):
            dibujar_votos(pantalla, self.app.fuentes, self.app.temas.actual, self.resultado, self.candidatos, s.final(),
                          self.pagina - 1, self.paginas)
            return
        dibujar_resultado(pantalla, self.app.fuentes, self.app.temas.actual, self.resultado, self.candidatos,
                          s.ciudad.score, min(1.0, self.t / DURACION_CONTEO), jugadores, s.bitacora)
