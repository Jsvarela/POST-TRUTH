"""Decorado del mundo (arboles, cesped, faroles, bancas) y ambiente animado: sin ventana."""
import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_MUNDO
from post_truth.models.mundo import MundoCiudad
from post_truth.views.decorado import distancia_a_lo_transitable, generar
from post_truth.views.mundo_view import EstadoMundo, dibujar_mundo
from post_truth.views.theme import TEMAS


class GenerarDecoradoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m = MundoCiudad.cargar(RUTA_MUNDO)
        self.d = generar(self.m)

    def puntos(self):
        d = self.d
        return ([(x, y) for x, y, _ in d.cesped] + [(x, y) for x, y, _, _ in d.arboles]
                + [(x, y) for x, y, _, _ in d.arbustos] + [(x, y) for x, y, _ in d.faroles] + list(d.bancas))

    def test_siempre_sale_el_mismo_pueblo(self) -> None:
        self.assertEqual(generar(self.m), self.d)
        self.assertNotEqual(generar(self.m, semilla=1), self.d)

    def test_hay_de_todo(self) -> None:
        d = self.d
        self.assertGreater(len(d.cesped), 150)
        self.assertGreaterEqual(len(d.arboles), 30)
        self.assertGreaterEqual(len(d.arbustos), 15)
        self.assertGreaterEqual(len(d.faroles), 6)
        self.assertGreaterEqual(len(d.bancas), len(self.m.plazas))

    def test_nada_cae_sobre_calles_plazas_ni_edificios_ni_fuera_del_mundo(self) -> None:
        ancho, alto = self.m.tamano
        for x, y in self.puntos():
            self.assertTrue(0 < x < ancho and 0 < y < alto, (x, y))
            self.assertFalse(self.m.es_transitable((x, y)), (x, y))
            for e in self.m.edificios:
                ex, ey, ew, eh = e.rect
                self.assertFalse(ex <= x <= ex + ew and ey <= y <= ey + eh, (e.zona, x, y))

    def test_los_arboles_no_se_pisan_y_dejan_sitio_al_tronco(self) -> None:
        arboles = [(x, y) for x, y, _, _ in self.d.arboles]
        for i, a in enumerate(arboles):
            self.assertGreaterEqual(distancia_a_lo_transitable(self.m, a), 48)
            for b in arboles[i + 1:]:
                self.assertGreaterEqual(math.dist(a, b), 130)

    def test_los_faroles_bordean_las_calles(self) -> None:
        for x, y, _ in self.d.faroles:
            self.assertLess(distancia_a_lo_transitable(self.m, (x, y)), 40, (x, y))


class AmbienteAnimadoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((1280, 800))
        from post_truth.views.componentes import Fuentes
        cls.fuentes = Fuentes.crear()
        cls.m = MundoCiudad.cargar(RUTA_MUNDO)
        cls.deco = generar(cls.m)

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def imagen(self, t: float, tema: str = "normal", decorado=True, centro=None) -> bytes:
        estado = EstadoMundo(decorado=self.deco if decorado else None, t=t, centro_camara=centro)
        dibujar_mundo(self.pantalla, self.fuentes, TEMAS[tema], self.m, estado)
        return pygame.image.tobytes(self.pantalla, "RGB")

    def test_el_decorado_cambia_la_imagen_en_los_3_temas(self) -> None:
        for tema in TEMAS:
            self.assertNotEqual(self.imagen(0, tema), self.imagen(0, tema, decorado=False), tema)

    def test_el_ambiente_se_mueve_con_el_tiempo_y_se_repite_igual(self) -> None:
        centro = self.m.plazas["parque"].pos                              # zona con muchos arboles
        a, b = self.imagen(0.0, centro=centro), self.imagen(0.7, centro=centro)
        self.assertNotEqual(a, b)                                          # viento, faroles, ventanas...
        self.assertEqual(self.imagen(0.7, centro=centro), b)              # mismo t, misma imagen (depende de t, no de los FPS)

    def test_el_proveedor_recibe_las_piezas_del_decorado(self) -> None:
        from post_truth.views.arte_mundo import ArteFormas
        llamadas = []

        class ArteEspia(ArteFormas):
            def __getattribute__(self, nombre):
                if not nombre.startswith("_"):
                    llamadas.append(nombre)
                return super().__getattribute__(nombre)
        estado = EstadoMundo(decorado=self.deco, t=3.0, centro_camara=self.m.plazas["plaza"].pos)
        dibujar_mundo(self.pantalla, self.fuentes, TEMAS["normal"], self.m, estado, arte=ArteEspia())
        self.assertTrue({"cesped", "arbol", "arbusto", "farol", "banca"} <= set(llamadas), set(llamadas))

    def test_los_pajaros_cruzan_la_pantalla(self) -> None:
        from post_truth.views.arte_mundo import ArteFormas
        vistos = []

        class Contador(ArteFormas):
            def pajaro(self, pantalla, tema, pos, tam, aleteo):
                vistos.append(pos)
        arte = Contador()
        for t in range(0, 120, 2):                                         # dos minutos de partida
            estado = EstadoMundo(decorado=self.deco, t=float(t), centro_camara=self.m.plazas["colegio"].pos)
            dibujar_mundo(self.pantalla, self.fuentes, TEMAS["normal"], self.m, estado, arte=arte)
        self.assertTrue(vistos)


if __name__ == "__main__":
    unittest.main()
