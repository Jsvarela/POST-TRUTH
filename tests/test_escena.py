import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # sin ventana
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, FIN
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.pygame_app import App


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def clic(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


class FlujoEscenaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()

    def tearDown(self) -> None:
        pygame.quit()

    def _a_la_escena(self, rol_tecla: int = pygame.K_1, genero_tecla: int = pygame.K_2) -> None:
        tecla(self.app, pygame.K_RETURN)   # menu -> seleccion
        tecla(self.app, rol_tecla)         # rol
        tecla(self.app, genero_tecla)      # genero -> escena

    def test_menu_seleccion_escena(self) -> None:
        self._a_la_escena(pygame.K_3, pygame.K_1)
        self.assertEqual(self.app.personaje, Personaje(Role.INFLUENCER, Genero.HOMBRE))
        self.assertIs(self.app.estados._actual, self.app.estados._estados["escena"])

    def test_esc_retrocede_de_a_una_fase(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        sel = self.app.estados._actual
        tecla(self.app, pygame.K_2)
        self.assertEqual(sel.fase, "genero")
        tecla(self.app, pygame.K_ESCAPE)
        self.assertEqual(sel.fase, "rol")
        tecla(self.app, pygame.K_ESCAPE)
        self.assertIs(self.app.estados._actual, self.app.estados._estados["menu"])

    def test_decision_aplica_impacto_y_muestra_consecuencia(self) -> None:
        self.app.estados._estados["escena"].rng = random.Random(1)
        self._a_la_escena()
        escena = self.app.estados._actual
        self.assertEqual(escena.fase, DECIDIENDO)
        antes = escena.ciudad.as_display_rows()
        tecla(self.app, pygame.K_1)
        self.assertEqual(escena.fase, CONSECUENCIA)
        self.assertNotEqual(escena.ciudad.as_display_rows(), antes)
        self.assertEqual(escena.dialogo.hablante, "Consecuencia")
        self.assertIsNotNone(escena.impacto)

    def test_clic_con_mouse_en_boton(self) -> None:
        self._a_la_escena()
        escena = self.app.estados._actual
        clic(self.app, escena.botones[1].rect.center)
        self.assertEqual(escena.fase, CONSECUENCIA)

    def test_botones_salen_del_arbol(self) -> None:
        self._a_la_escena()
        escena = self.app.estados._actual
        self.assertEqual([b.texto.split(". ", 1)[1] for b in escena.botones],
                         [n.label for n in escena.arbol.root.children[:4]])

    def test_rol_cambia_el_resultado(self) -> None:
        """Mismo evento y misma decision: el influencer amplifica mas que el ciudadano."""
        resultados = {}
        for nombre, tecla_rol in (("ciudadano", pygame.K_1), ("influencer", pygame.K_3)):
            self.app.estados._estados["escena"].rng = random.Random(1)
            self._a_la_escena(tecla_rol)
            escena = self.app.estados._actual
            tecla(self.app, pygame.K_1)  # Compartir / primera rama
            resultados[nombre] = abs(escena.impacto.misinformation)
            self.app.estados.cambiar("menu")
        self.assertGreater(resultados["influencer"], resultados["ciudadano"])

    def test_partida_completa_termina_en_fin(self) -> None:
        self._a_la_escena()
        escena = self.app.estados._actual
        for _ in range(len(escena.arboles)):
            tecla(self.app, pygame.K_1)       # decidir
            self.app.estados.update(0.016)
            self.app.estados.draw(self.app.pantalla)
            tecla(self.app, pygame.K_RETURN)  # continuar
        self.assertEqual(escena.fase, FIN)
        tecla(self.app, pygame.K_RETURN)      # volver al menu
        self.assertIs(self.app.estados._actual, self.app.estados._estados["menu"])

    def test_dibuja_en_todos_los_temas_y_roles(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            for rol_tecla in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.app.estados.cambiar("menu")
                self._a_la_escena(rol_tecla)
                self.app.estados.update(0.5)
                self.app.estados.draw(self.app.pantalla)
                tecla(self.app, pygame.K_2)
                self.app.estados.draw(self.app.pantalla)


if __name__ == "__main__":
    unittest.main()
