"""Modelo de animacion del personaje (puro): nombres para la hoja de sprites, direccion, estado y cuadros."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.models.animacion import ANIMACIONES, CUADROS, AnimacionPersonaje


class AnimacionTest(unittest.TestCase):
    def test_los_nombres_son_los_de_la_hoja_de_sprites(self) -> None:
        self.assertEqual(ANIMACIONES, ("idle_abajo", "idle_arriba", "idle_izquierda", "idle_derecha",
                                       "caminar_abajo", "caminar_arriba", "caminar_izquierda", "caminar_derecha"))
        self.assertEqual(AnimacionPersonaje().nombre, "idle_abajo")

    def test_la_direccion_sale_de_las_teclas(self) -> None:
        a = AnimacionPersonaje()
        for (dx, dy), esperado in (((1, 0), "derecha"), ((-1, 0), "izquierda"), ((0, -1), "arriba"),
                                   ((0, 1), "abajo"), ((2, 1), "derecha"), ((1, -3), "arriba")):
            a.actualizar(dx, dy, 1.0, 0.1)
            self.assertEqual(a.nombre, f"caminar_{esperado}", (dx, dy))

    def test_en_diagonal_exacta_conserva_la_direccion_si_es_una_de_las_dos(self) -> None:
        a = AnimacionPersonaje("arriba")
        a.actualizar(1, -1, 1.0, 0.1)
        self.assertEqual(a.direccion, "arriba")
        a = AnimacionPersonaje("abajo")
        a.actualizar(1, -1, 1.0, 0.1)
        self.assertEqual(a.direccion, "derecha")          # ninguna de las dos: gana la horizontal

    def test_sin_teclas_o_contra_una_pared_queda_quieto_mirando_hacia_alla(self) -> None:
        a = AnimacionPersonaje()
        a.actualizar(-1, 0, 5.0, 0.1)
        a.actualizar(0, 0, 0.0, 0.1)
        self.assertEqual(a.nombre, "idle_izquierda")
        a.actualizar(0, -1, 0.0, 0.1)                     # empuja una pared hacia arriba: gira, pero no camina
        self.assertEqual(a.nombre, "idle_arriba")

    def test_el_cuadro_avanza_igual_a_30_y_60_fps(self) -> None:
        for fps in (30, 60):
            a = AnimacionPersonaje()
            vistos = []
            for _ in range(fps):                           # un segundo caminando
                a.actualizar(1, 0, 1.0, 1 / fps)
                vistos.append(a.cuadro)
            self.assertEqual(set(vistos), set(range(CUADROS["caminar"])), fps)
            self.assertEqual(a.cuadro, int(a.t * 8) % 4)

    def test_cambiar_de_estado_empieza_en_el_primer_cuadro(self) -> None:
        a = AnimacionPersonaje()
        for _ in range(7):
            a.actualizar(1, 0, 1.0, 0.05)
        a.actualizar(0, 0, 0.0, 0.01)
        self.assertEqual(a.cuadro, 0)

    def test_ida_y_vuelta_y_datos_invalidos(self) -> None:
        a = AnimacionPersonaje("derecha", "caminar", 0.37)
        self.assertEqual(AnimacionPersonaje.from_dict(json.loads(json.dumps(a.to_dict()))), a)
        with self.assertRaises(ValueError):
            AnimacionPersonaje("diagonal")


if __name__ == "__main__":
    unittest.main()
