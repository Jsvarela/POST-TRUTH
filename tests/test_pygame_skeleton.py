import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # sin ventana
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import pygame
except ImportError:  # pygame es opcional para las pruebas de arboles
    pygame = None


@unittest.skipIf(pygame is None, "pygame no instalado")
class PygameSkeletonTest(unittest.TestCase):
    def test_flujo_menu_juego_y_decision(self) -> None:
        from post_truth.pygame_app import App

        app = App()
        app.estados.cambiar("juego")  # GameState ya no esta en el flujo del menu, se prueba directo
        juego = app.estados._actual
        antes = juego.ciudad.verified_information
        app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))  # Verificar
        self.assertGreater(juego.ciudad.verified_information, antes)
        app.estados.update(0.016)
        app.estados.draw(app.pantalla)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
