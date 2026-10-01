import itertools
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_INTRO
from post_truth.models.intro import ACCESORIOS, AspectoRetrato, Intro, PEINADOS
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import TEMAS

RECT = pygame.Rect(10, 10, 154, 204)


class RetratoViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((180, 224))

    def _imagen(self, aspecto: AspectoRetrato, tema_id: str = "normal") -> bytes:
        tema = TEMAS[tema_id]
        self.pantalla.fill(tema.fondo)
        dibujar_retrato(self.pantalla, aspecto, tema, RECT)
        return pygame.image.tobytes(self.pantalla, "RGB")

    def test_todas_las_combinaciones_de_peinado_y_accesorio_se_dibujan_en_los_3_temas(self) -> None:
        for tema, peinado, accesorio in itertools.product(TEMAS, PEINADOS, ACCESORIOS):
            self._imagen(AspectoRetrato(1, 0, peinado, accesorio, 2), tema)

    def test_los_cuatro_candidatos_se_ven_distintos_en_cada_tema(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        for tema in TEMAS:
            imagenes = {self._imagen(c.aspecto, tema) for c in intro.candidatos}
            self.assertEqual(len(imagenes), 4, tema)

    def test_se_distinguen_por_forma_y_no_solo_por_color(self) -> None:
        """Mismo color de campana y de piel: cambiar peinado o accesorio cambia el dibujo."""
        base = AspectoRetrato(0, 0, "corto", "lentes", 1)
        self.assertNotEqual(self._imagen(base), self._imagen(AspectoRetrato(0, 0, "largo", "lentes", 1)))
        self.assertNotEqual(self._imagen(base), self._imagen(AspectoRetrato(0, 0, "corto", "corbata", 1)))

    def test_el_dibujo_no_se_sale_del_marco(self) -> None:
        self.pantalla.fill((1, 2, 3))
        dibujar_retrato(self.pantalla, AspectoRetrato(0, 0, "largo", "bufanda", 0), TEMAS["normal"], RECT)
        for x, y in ((2, 2), (170, 5), (5, 215), (172, 218)):
            self.assertEqual(self.pantalla.get_at((x, y))[:3], (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
