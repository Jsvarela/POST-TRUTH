"""Personaje animado del mundo caminable: 8 animaciones x cuadros, 4 roles x 2 generos, 3 temas (sin ventana)."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.models import Role
from post_truth.models.animacion import ANIMACIONES, CUADROS
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.personaje_view import dibujar_personaje_mundo
from post_truth.views.theme import TEMAS

ALTO = 96
TAM = (80, 120)
PIES = (40, 110)


class PersonajeMundoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def imagen(self, pj: Personaje, nombre: str, cuadro: int = 0, tema: str = "normal") -> pygame.Surface:
        s = pygame.Surface(TAM)
        s.fill(TEMAS[tema].suelo)
        dibujar_personaje_mundo(s, pj, TEMAS[tema], PIES, ALTO, nombre, cuadro)
        return s

    def bytes_(self, *args, **kw) -> bytes:
        return pygame.image.tobytes(self.imagen(*args, **kw), "RGB")

    def test_todas_las_animaciones_cuadros_roles_generos_y_temas_dibujan_algo(self) -> None:
        for tema in TEMAS:
            vacio = pygame.Surface(TAM)
            vacio.fill(TEMAS[tema].suelo)
            vacio = pygame.image.tobytes(vacio, "RGB")
            for rol in Role:
                for genero in Genero:
                    pj = Personaje(rol, genero)
                    for nombre in ANIMACIONES:
                        for c in range(CUADROS[nombre.split("_")[0]]):
                            self.assertNotEqual(self.bytes_(pj, nombre, c, tema), vacio, (tema, pj, nombre, c))

    def test_las_cuatro_direcciones_se_ven_distintas(self) -> None:
        for rol in Role:
            pj = Personaje(rol, Genero.HOMBRE)
            imagenes = {self.bytes_(pj, f"idle_{d}") for d in ("abajo", "arriba", "izquierda", "derecha")}
            self.assertEqual(len(imagenes), 4, rol)

    def test_izquierda_es_el_espejo_de_derecha(self) -> None:
        pj = Personaje(Role.JOURNALIST, Genero.MUJER)
        for c in range(4):
            derecha = self.imagen(pj, "caminar_derecha", c)
            izquierda = self.imagen(pj, "caminar_izquierda", c)
            # se compara con el espejo de la derecha; la sombra (dibujada aparte) puede variar un pixel en el borde
            espejo = pygame.transform.flip(derecha, True, False)
            distintos = sum(espejo.get_at((x, y)) != izquierda.get_at((x, y))
                            for x in range(TAM[0]) for y in range(TAM[1]))
            self.assertLess(distintos, TAM[0] * TAM[1] // 100, c)

    def test_caminar_cambia_entre_cuadros_y_quieto_respira(self) -> None:
        pj = Personaje(Role.INFLUENCER, Genero.MUJER)
        for d in ("abajo", "arriba", "derecha"):
            # 4 cuadros: dos con las piernas abiertas (distintos) y dos cruzandose (pueden coincidir de frente)
            self.assertGreaterEqual(len({self.bytes_(pj, f"caminar_{d}", c) for c in range(4)}), 3, d)
            self.assertNotEqual(self.bytes_(pj, f"caminar_{d}", 0), self.bytes_(pj, f"caminar_{d}", 2), d)
            self.assertNotEqual(self.bytes_(pj, f"idle_{d}", 0), self.bytes_(pj, f"idle_{d}", 1), d)

    def test_respeta_rol_y_genero(self) -> None:
        for d in ("abajo", "arriba", "derecha"):
            imagenes = {self.bytes_(Personaje(r, g), f"idle_{d}") for r in Role for g in Genero}
            self.assertEqual(len(imagenes), 8, d)

    def test_la_sombra_queda_bajo_los_pies(self) -> None:
        tema = TEMAS["normal"]
        s = self.imagen(Personaje(Role.CITIZEN, Genero.HOMBRE), "idle_abajo")
        # a los lados de los pies (fuera de las piernas) solo puede estar la sombra
        self.assertNotEqual(s.get_at((PIES[0] - 16, PIES[1] - 2))[:3], tema.suelo)
        self.assertEqual(s.get_at((PIES[0] - 16, PIES[1] - 30))[:3], tema.suelo)

    def test_los_pies_estan_donde_se_pide(self) -> None:
        tema = TEMAS["normal"]
        s = self.imagen(Personaje(Role.CANDIDATE, Genero.HOMBRE), "idle_abajo")
        filas = [y for y in range(TAM[1]) if any(s.get_at((x, y))[:3] != tema.suelo for x in range(TAM[0]))]
        self.assertLessEqual(max(filas), PIES[1] + 2)
        self.assertGreaterEqual(min(filas), PIES[1] - ALTO - 2)


if __name__ == "__main__":
    unittest.main()
