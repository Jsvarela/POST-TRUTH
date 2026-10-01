import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_GRAFO_CIUDAD
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.mapa_view import EstadoMapa, dibujar_mapa, zona_en
from post_truth.views.theme import TEMAS
from post_truth.views.zona_view import dibujar_fondo_zona

RECT_MAPA = pygame.Rect(0, 0, 270, 262)


class ZonasViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((1024, 640))
        cls.fuentes = Fuentes.crear()
        cls.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    def test_cada_zona_tiene_un_fondo_distinto(self) -> None:
        tema = TEMAS["normal"]
        rect = pygame.Rect(0, 57, 1024, 347)
        imagenes = []
        for z in self.ciudad.zonas():
            self.pantalla.fill((0, 0, 0))
            dibujar_fondo_zona(self.pantalla, z.id, tema, rect)
            imagenes.append(pygame.image.tobytes(self.pantalla.subsurface(rect), "RGB"))
        self.assertEqual(len(set(imagenes)), len(imagenes))   # no hay dos fondos iguales

    def test_fondos_en_todos_los_temas_y_zona_desconocida(self) -> None:
        rect = pygame.Rect(0, 57, 1024, 347)
        for tema in TEMAS.values():
            for z in [z.id for z in self.ciudad.zonas()] + ["zona-inventada"]:
                dibujar_fondo_zona(self.pantalla, z, tema, rect)

    def test_el_fondo_usa_solo_colores_del_tema(self) -> None:
        """Con colores distintos por tema, el mismo fondo cambia: nada esta fijo en la vista."""
        rect = pygame.Rect(0, 57, 1024, 347)
        dibujos = []
        for tema in TEMAS.values():
            self.pantalla.fill((0, 0, 0))
            dibujar_fondo_zona(self.pantalla, "plaza", tema, rect)
            dibujos.append(pygame.image.tobytes(self.pantalla.subsurface(rect), "RGB"))
        self.assertEqual(len(set(dibujos)), 3)

    def test_zona_en_acierta_en_el_centro_de_cada_nodo_y_falla_fuera(self) -> None:
        estado = EstadoMapa(self.ciudad, "plaza")
        from post_truth.views.mapa_view import _posiciones
        for id, punto in _posiciones(estado, RECT_MAPA).items():
            self.assertEqual(zona_en(estado, RECT_MAPA, punto), id)
        self.assertIsNone(zona_en(estado, RECT_MAPA, (RECT_MAPA.right - 1, RECT_MAPA.centery)))

    def test_mapa_dibuja_todos_los_estados_en_todos_los_temas(self) -> None:
        estado = EstadoMapa(self.ciudad, "plaza", zona_noticia="colegio", infectadas={"colegio", "barrio"},
                            en_riesgo={"parque", "plaza"}, alcanzables=self.ciudad.vecinos("plaza"))
        for tema in TEMAS.values():
            dibujar_mapa(self.pantalla, self.fuentes, tema, RECT_MAPA, estado)
            dibujar_mapa(self.pantalla, self.fuentes, tema, RECT_MAPA, EstadoMapa(self.ciudad, "colegio"))

    def test_la_zona_actual_se_distingue_de_las_demas(self) -> None:
        tema = TEMAS["normal"]
        a = EstadoMapa(self.ciudad, "plaza")
        b = EstadoMapa(self.ciudad, "parque")
        self.pantalla.fill((0, 0, 0))
        dibujar_mapa(self.pantalla, self.fuentes, tema, RECT_MAPA, a)
        img_a = pygame.image.tobytes(self.pantalla.subsurface(RECT_MAPA), "RGB")
        self.pantalla.fill((0, 0, 0))
        dibujar_mapa(self.pantalla, self.fuentes, tema, RECT_MAPA, b)
        img_b = pygame.image.tobytes(self.pantalla.subsurface(RECT_MAPA), "RGB")
        self.assertNotEqual(img_a, img_b)


if __name__ == "__main__":
    unittest.main()
