import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_GRAFO_SOCIAL
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import COMPARTIR, REPORTAR, simular_decision
from post_truth.views.componentes import Fuentes
from post_truth.views.grafo_view import DURACION_OLA, ENTRADA, AnimacionPropagacion
from post_truth.views.theme import TEMAS


def animacion(tipo: str, semilla: int = 11) -> AnimacionPropagacion:
    g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
    sim = simular_decision(g, tipo, True, "jugador", "tomas", random.Random(semilla))
    return AnimacionPropagacion(g, sim)


class AnimacionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((700, 380))
        cls.fuentes = Fuentes.crear()

    def test_avanza_con_dt_ola_por_ola(self) -> None:
        a = animacion(COMPARTIR)
        self.assertEqual(a._olas_completas(), 0)
        a.update(ENTRADA + DURACION_OLA * 1.01)
        self.assertEqual(a._olas_completas(), 1)
        self.assertFalse(a.terminada)
        # cada paso de dt solo suma tiempo; nunca bloquea
        for _ in range(int(a.duracion * 60) + 5):
            a.update(1 / 60)
        self.assertTrue(a.terminada)
        self.assertEqual(a._olas_completas(), a.resultado.n_olas)

    def test_saltar_termina_y_narra_el_resumen(self) -> None:
        a = animacion(COMPARTIR)
        a.saltar()
        self.assertTrue(a.terminada)
        self.assertIn("personas", a.narracion())

    def test_reportar_no_propaga_pero_dura_lo_suficiente_para_verse(self) -> None:
        a = animacion(REPORTAR)
        self.assertEqual(a.resultado.n_olas, 0)
        self.assertGreater(a.duracion, ENTRADA)
        self.assertIn("cortan", a.narracion())

    def test_dibuja_en_todos_los_temas_en_cada_instante(self) -> None:
        for tipo in (COMPARTIR, REPORTAR):
            for tema in TEMAS.values():
                a = animacion(tipo)
                while not a.terminada:
                    a.draw(self.pantalla, self.fuentes, tema, pygame.Rect(18, 8, 664, 364))
                    a.update(0.25)
                a.draw(self.pantalla, self.fuentes, tema, pygame.Rect(18, 8, 664, 364))


if __name__ == "__main__":
    unittest.main()
