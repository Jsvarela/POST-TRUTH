"""Vista de la introduccion: todas las laminas, en los 3 temas y en todos los instantes."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_GRAFO_CIUDAD, RUTA_INTRO
from post_truth.models.intro import Intro
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import CajaDialogo, Fuentes
from post_truth.views.intro_view import TAMANO_LIENZO, _horizonte, dibujar_intro
from post_truth.views.theme import TEMAS

RECT_SUB = pygame.Rect(24, 492, 976, 116)
INSTANTES = (0.0, 0.3, 1.0, 2.5, 5.0, 9.0, 20.0)  # entrando, apareciendo, mantenida, mapa en otra zona...


class IntroVistaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((1024, 640))
        cls.fuentes = Fuentes.crear()
        cls.intro = Intro.cargar(RUTA_INTRO)
        cls.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        cls.lienzo = pygame.Surface(TAMANO_LIENZO)

    def _dibujar(self, i: int, tema_id: str, t: float, alfa: float = 255, avance_texto: float | None = None) -> bytes:
        tema = TEMAS[tema_id]
        dialogo = CajaDialogo(RECT_SUB, 45)
        lamina = self.intro.laminas[i]
        dialogo.set_texto(lamina.texto, lamina.titulo)
        if avance_texto is None:
            dialogo.completar()
        else:
            dialogo.update(avance_texto)
        dibujar_intro(self.pantalla, self.lienzo, self.fuentes, tema, self.intro, self.ciudad, i, t, alfa,
                      dialogo, "pie")
        return pygame.image.tobytes(self.pantalla, "RGB")

    def test_cada_lamina_se_dibuja_en_los_3_temas_y_en_todos_los_instantes(self) -> None:
        for tema in TEMAS:
            for i in range(len(self.intro.laminas)):
                for t in INSTANTES:
                    self._dibujar(i, tema, t)

    def test_las_laminas_son_distintas_entre_si(self) -> None:
        imagenes = {self._dibujar(i, "normal", 6.0) for i in range(len(self.intro.laminas))}
        self.assertEqual(len(imagenes), len(self.intro.laminas))

    def test_el_dibujo_cambia_con_el_tiempo_pero_no_con_el_fundido_el_subtitulo(self) -> None:
        self.assertNotEqual(self._dibujar(0, "normal", 0.2), self._dibujar(0, "normal", 3.0))   # animacion
        self.assertNotEqual(self._dibujar(2, "normal", 1.0), self._dibujar(2, "normal", 4.0))   # posts de Civitas

    def test_el_fundido_oculta_el_dibujo_pero_el_subtitulo_sigue_visible(self) -> None:
        tema = TEMAS["normal"]
        a = self._dibujar(0, "normal", 3.0, alfa=255)
        invisible = self._dibujar(0, "normal", 3.0, alfa=0)
        tenue = self._dibujar(0, "normal", 3.0, alfa=100)
        self.assertEqual(len({a, invisible, tenue}), 3)         # el alfa produce 3 resultados distintos
        # Con alfa 0 el area del dibujo es del color de fondo del tema...
        self.pantalla.fill((9, 9, 9))
        dibujar_intro(self.pantalla, self.lienzo, self.fuentes, tema, self.intro, self.ciudad, 0, 3.0, 0,
                      self._dialogo_completo(0), "pie")
        self.assertEqual(self.pantalla.get_at((500, 250))[:3], tema.fondo)
        # ...y la caja del subtitulo se pinta igual (con el color de panel del tema)
        self.assertEqual(self.pantalla.get_at((RECT_SUB.x + 40, RECT_SUB.bottom - 8))[:3], tema.panel)

    def _dialogo_completo(self, i: int) -> CajaDialogo:
        d = CajaDialogo(RECT_SUB, 45)
        d.set_texto(self.intro.laminas[i].texto, self.intro.laminas[i].titulo)
        d.completar()
        return d

    def test_el_subtitulo_se_escribe_poco_a_poco(self) -> None:
        a = self._dibujar(0, "normal", 1.0, avance_texto=0.2)
        b = self._dibujar(0, "normal", 1.0, avance_texto=1.5)
        c = self._dibujar(0, "normal", 1.0)
        self.assertEqual(len({a, b, c}), 3)

    def test_el_mapa_resalta_una_zona_distinta_con_el_paso_del_tiempo(self) -> None:
        vistas = {self._dibujar(1, "normal", t) for t in (0.5, 4.0, 7.0, 10.0, 13.0)}
        self.assertEqual(len(vistas), 5)                        # 5 zonas, 5 imagenes distintas

    def test_los_colores_salen_del_tema(self) -> None:
        imagenes = {self._dibujar(3, tema, 5.0) for tema in TEMAS}
        self.assertEqual(len(imagenes), 3)

    def test_el_horizonte_enciende_ventanas_con_el_tiempo(self) -> None:
        tema = TEMAS["normal"]
        _horizonte(self.lienzo, tema, 0.0)
        antes = pygame.image.tobytes(self.lienzo, "RGB")
        _horizonte(self.lienzo, tema, 6.0)
        self.assertNotEqual(antes, pygame.image.tobytes(self.lienzo, "RGB"))


if __name__ == "__main__":
    unittest.main()
