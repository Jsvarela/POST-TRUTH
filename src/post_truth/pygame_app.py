"""Game loop de Pygame + StateManager (migracion desde Tkinter)."""
import pygame

from post_truth.config import ANCHO, ALTO, FPS, TITULO
from post_truth.controllers.game_state import GameState
from post_truth.controllers.menu_state import MenuState
from post_truth.controllers.state_manager import StateManager
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import GestorTemas


class App:
    """Contenedor de recursos compartidos entre estados."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITULO)
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        self.reloj = pygame.time.Clock()
        self.fuente = pygame.font.SysFont("arial", 24)
        self.fuentes = Fuentes.crear()  # tamanos extra para la UI de novela visual
        self.temas = GestorTemas()
        self.corriendo = True
        self.estados = StateManager()
        self.estados.registrar("menu", MenuState(self))
        self.estados.registrar("juego", GameState(self))
        self.estados.cambiar("menu")

    def run(self) -> None:
        while self.corriendo:
            dt = self.reloj.tick(FPS) / 1000.0  # segundos del frame (limita a 60 FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.corriendo = False
                self.estados.handle_event(event)
            self.estados.update(dt)
            self.estados.draw(self.pantalla)
            pygame.display.flip()
        pygame.quit()
