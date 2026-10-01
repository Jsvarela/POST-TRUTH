import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.views.componentes import Boton, CajaDialogo, Fuentes, ajustar_texto
from post_truth.views.theme import TEMAS


class ComponentesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((400, 300))
        cls.fuentes = Fuentes.crear()

    def test_ajustar_texto_respeta_ancho(self) -> None:
        texto = "El candidato quiere cerrar el colegio central si gana la alcaldia"
        lineas = ajustar_texto(texto, self.fuentes.normal, 200)
        self.assertGreater(len(lineas), 1)
        for linea in lineas:
            self.assertLessEqual(self.fuentes.normal.size(linea)[0], 200)
        self.assertEqual(" ".join(lineas), texto)

    def test_boton_hover_y_clic(self) -> None:
        clics: list[int] = []
        b = Boton(pygame.Rect(10, 10, 100, 40), "Ok", lambda: clics.append(1))
        b.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(20, 20), rel=(0, 0), buttons=(0, 0, 0)))
        self.assertTrue(b.hover)
        b.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(20, 20), button=1))
        b.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(20, 20), button=1))
        self.assertEqual(clics, [1])

    def test_boton_soltar_fuera_no_dispara(self) -> None:
        clics: list[int] = []
        b = Boton(pygame.Rect(10, 10, 100, 40), "Ok", lambda: clics.append(1))
        b.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(20, 20), button=1))
        b.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(300, 250), button=1))
        self.assertEqual(clics, [])

    def test_boton_atajo(self) -> None:
        clics: list[int] = []
        b = Boton(pygame.Rect(0, 0, 50, 20), "x", lambda: clics.append(1), atajo=pygame.K_1)
        b.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
        self.assertEqual(clics, [1])

    def test_dialogo_se_revela_con_dt(self) -> None:
        d = CajaDialogo(pygame.Rect(0, 0, 300, 100), caracteres_por_segundo=10)
        d.set_texto("0123456789")
        d.update(0.5)
        self.assertFalse(d.terminado)
        d.update(1.0)
        self.assertTrue(d.terminado)

    def test_dibuja_en_todos_los_temas(self) -> None:
        d = CajaDialogo(pygame.Rect(0, 0, 300, 100))
        d.set_texto("Hola mundo", "Civitas")
        b = Boton(pygame.Rect(0, 150, 100, 40), "Boton con un texto bastante largo", lambda: None)
        for tema in TEMAS.values():
            d.draw(self.pantalla, self.fuentes, tema)
            b.draw(self.pantalla, self.fuentes.normal, tema)


if __name__ == "__main__":
    unittest.main()
