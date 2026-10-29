"""Ayuda (F2 desde cualquier pantalla, o Ayuda en el menu): capa encima del juego, que queda en pausa debajo, como el
modo sustentacion. Se abre en la seccion de la pantalla donde se pidio."""
import pygame

from post_truth.models.ayuda import indice, secciones
from post_truth.views.ayuda_view import dibujar_ayuda, lineas, rect_entrada, visibles

CONTEXTO = {"MenuState": "objetivo", "MundoState": "controles", "LugarState": "noticias", "EscenaState": "noticias",
            "InvestigacionState": "noticias", "TelefonoState": "red", "MinijuegoState": "minijuegos",
            "ResumenState": "credibilidad", "FaseState": "mapa", "ResultadoState": "ganar",
            "ConectarState": "multijugador", "SalaState": "multijugador", "SeleccionState": "roles"}


class Ayuda:
    def __init__(self, app) -> None:
        self.app = app
        self.activo = False
        self.actual, self.desde = 0, 0

    def abrir(self, seccion: str | None = None) -> None:
        """Sin seccion: la que corresponde a la pantalla de abajo."""
        actual = self.app.estados.actual
        self.actual = indice(seccion or CONTEXTO.get(type(actual).__name__, "objetivo"))
        self.desde, self.activo = 0, True

    def alternar(self) -> None:
        if self.activo:
            self.activo = False
        else:
            self.abrir()

    def _mover(self, paso: int) -> None:
        self.actual, self.desde = (self.actual + paso) % len(secciones()), 0

    def _desplazar(self, paso: int) -> None:
        sobra = len(lineas(self.app.fuentes, secciones()[self.actual])) - visibles(self.app.fuentes)
        self.desde = max(0, min(max(0, sobra), self.desde + paso))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_F2, pygame.K_ESCAPE):
                self.activo = False
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._mover(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
                self._mover(1)
            elif event.key in (pygame.K_PAGEDOWN, pygame.K_RIGHT, pygame.K_d):
                self._desplazar(visibles(self.app.fuentes) - 1)
            elif event.key in (pygame.K_PAGEUP, pygame.K_LEFT, pygame.K_a):
                self._desplazar(1 - visibles(self.app.fuentes))
        elif event.type == pygame.MOUSEWHEEL:
            self._desplazar(-3 * event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(secciones())):
                if rect_entrada(i).collidepoint(event.pos):
                    self.actual, self.desde = i, 0

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_ayuda(pantalla, self.app.fuentes, self.app.temas.actual, secciones(), self.actual, self.desde)
