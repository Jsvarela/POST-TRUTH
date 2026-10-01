import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_EVENTOS
from post_truth.decision_tree import load_trees
from post_truth.models.pistas import Investigacion, ZonaTarjeta
from post_truth.models.publicacion import Avatar
from post_truth.views.componentes import Fuentes
from post_truth.views.tarjeta_civitas_view import (TECLAS_PISTA, _avatar, _layout, dibujar_tarjeta, pista_con_tecla,
                                                   zona_en)
from post_truth.views.theme import TEMAS

RECT = pygame.Rect(10, 10, 372, 312)


class TarjetaViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((400, 340))
        cls.fuentes = Fuentes.crear()
        cls.eventos = [a.event for a in load_trees(RUTA_EVENTOS)]

    def _imagen(self, evento, inv: Investigacion, tema_id: str = "normal", hover=None) -> bytes:
        tema = TEMAS[tema_id]
        self.pantalla.fill(tema.panel)
        dibujar_tarjeta(self.pantalla, self.fuentes, tema, RECT, evento, inv, hover)
        return pygame.image.tobytes(self.pantalla, "RGB")

    def test_dibuja_las_5_noticias_en_los_3_temas_y_en_todos_los_estados(self) -> None:
        for tema in TEMAS:
            for e in self.eventos:
                inv = Investigacion(e.clues, energia_max=9)
                for zona in [None] + [p.zona for p in e.clues]:
                    self._imagen(e, inv, tema, hover=zona)       # sin descubrir, con tooltip de costo
                for p in e.clues:
                    inv.investigar(p.id)
                for zona in [None] + [p.zona for p in e.clues]:
                    self._imagen(e, inv, tema, hover=zona)       # todo descubierto, con tooltip de hallazgo

    def test_las_noticias_se_ven_distintas(self) -> None:
        imagenes = {self._imagen(e, Investigacion(e.clues)) for e in self.eventos}
        self.assertEqual(len(imagenes), len(self.eventos))

    def test_investigar_cambia_el_dibujo_de_la_tarjeta(self) -> None:
        e = self.eventos[0]
        inv = Investigacion(e.clues)
        antes = self._imagen(e, inv)
        inv.investigar(e.clues[0].id)
        self.assertNotEqual(antes, self._imagen(e, inv))

    def test_el_mouse_sobre_una_zona_con_pista_la_resalta(self) -> None:
        e = self.eventos[0]
        inv = Investigacion(e.clues)
        self.assertNotEqual(self._imagen(e, inv), self._imagen(e, inv, hover=e.clues[0].zona))

    def test_los_colores_salen_del_tema(self) -> None:
        e = self.eventos[0]
        self.assertEqual(len({self._imagen(e, Investigacion(e.clues), tema) for tema in TEMAS}), 3)

    def test_zona_en_acierta_en_cada_zona_con_pista(self) -> None:
        for e in self.eventos:
            zonas = _layout(RECT)
            for p in e.clues:
                self.assertEqual(zona_en(RECT, zonas[p.zona].center, e), p.zona, (e.event_id, p.id))

    def test_las_zonas_sin_pista_y_los_clics_fuera_no_responden(self) -> None:
        e = self.eventos[0]                               # colegio-cerrado no tiene pista en el texto
        sin_pista = set(ZonaTarjeta) - {p.zona for p in e.clues}
        self.assertTrue(sin_pista)
        for zona in sin_pista:
            self.assertIsNone(zona_en(RECT, _layout(RECT)[zona].center, e))
        self.assertIsNone(zona_en(RECT, (5, 5), e))
        self.assertIsNone(zona_en(RECT, (RECT.right + 50, RECT.centery), e))

    def test_las_zonas_no_se_pisan_y_caben_en_la_tarjeta(self) -> None:
        zonas = list(_layout(RECT).values())
        for i, a in enumerate(zonas):
            self.assertTrue(RECT.contains(a), a)
            for b in zonas[i + 1:]:
                self.assertFalse(a.colliderect(b), (a, b))

    def test_teclas_de_pista(self) -> None:
        e = self.eventos[0]
        for i, p in enumerate(e.clues):
            self.assertEqual(pista_con_tecla(e, TECLAS_PISTA[i]), p)
            self.assertEqual(pista_con_tecla(e, TECLAS_PISTA[i].lower()), p)
        self.assertIsNone(pista_con_tecla(e, "Z"))

    def test_los_tres_tipos_de_avatar_son_distintos(self) -> None:
        tema = TEMAS["normal"]
        retrato = next(e.author.avatar for e in self.eventos if e.author.avatar.tipo == "retrato")
        imagenes = set()
        for avatar in (retrato, Avatar("anonimo", 2), Avatar("institucional", 2)):
            self.pantalla.fill((0, 0, 0))
            _avatar(self.pantalla, self.fuentes, tema, avatar, "@alguien", pygame.Rect(10, 10, 48, 48))
            imagenes.add(pygame.image.tobytes(self.pantalla.subsurface(pygame.Rect(10, 10, 48, 48)), "RGB"))
        self.assertEqual(len(imagenes), 3)

    def test_el_titulo_del_evento_no_se_dibuja_para_no_delatar(self) -> None:
        """Titulos como "Rumor sobre el colegio" regalarian la respuesta antes de investigar."""
        import inspect
        import post_truth.views.tarjeta_civitas_view as vista
        self.assertNotIn("evento.title", inspect.getsource(vista.dibujar_tarjeta))


if __name__ == "__main__":
    unittest.main()
