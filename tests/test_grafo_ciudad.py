import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.structures.grafo_ciudad import GrafoCiudad, Zona


def linea() -> GrafoCiudad:
    """a - b - c - d en linea, y e aislada."""
    g = GrafoCiudad()
    for id in "abcde":
        g.agregar_zona(Zona(id, id.upper()))
    for x, y in ("ab", "bc", "cd"):
        g.agregar_conexion(x, y)
    return g


class EstructuraTest(unittest.TestCase):
    def test_conexiones_son_no_dirigidas(self) -> None:
        g = linea()
        self.assertEqual(g.vecinos("b"), ["a", "c"])
        self.assertIn("b", g.vecinos("a"))
        self.assertEqual(len(g.conexiones()), 3)   # cada una una sola vez

    def test_duplicados_y_lazos_son_invalidos(self) -> None:
        g = linea()
        with self.assertRaises(ValueError):
            g.agregar_zona(Zona("a", "otra"))
        with self.assertRaises(ValueError):
            g.agregar_conexion("a", "b")
        with self.assertRaises(ValueError):
            g.agregar_conexion("b", "a")           # misma conexion, otro orden
        with self.assertRaises(ValueError):
            g.agregar_conexion("a", "a")
        with self.assertRaises(KeyError):
            g.agregar_conexion("a", "zzz")

    def test_eliminar_conexion(self) -> None:
        g = linea()
        self.assertTrue(g.eliminar_conexion("a", "b"))
        self.assertFalse(g.eliminar_conexion("a", "b"))
        self.assertEqual(g.vecinos("a"), [])
        self.assertEqual(g.vecinos("b"), ["c"])

    def test_eliminar_zona_limpia_las_listas_de_los_vecinos(self) -> None:
        g = linea()
        g.eliminar_zona("b")
        self.assertNotIn("b", g)
        self.assertEqual(g.vecinos("a"), [])
        self.assertEqual(g.vecinos("c"), ["d"])
        with self.assertRaises(KeyError):
            g.vecinos("b")

    def test_roundtrip_dict_y_json(self) -> None:
        g = linea()
        g.zona_inicial = "c"
        copia = GrafoCiudad.from_dict(json.loads(json.dumps(g.to_dict())))
        self.assertEqual(copia.to_dict(), g.to_dict())
        self.assertEqual(copia.zona_inicial, "c")

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.structures.grafo_ciudad as modulo
        self.assertNotIn("pygame", vars(modulo))


class ConsultasTest(unittest.TestCase):
    def test_camino_bfs(self) -> None:
        g = linea()
        self.assertEqual(g.camino("a", "d"), ["a", "b", "c", "d"])
        self.assertEqual(g.camino("d", "a"), ["d", "c", "b", "a"])
        self.assertEqual(g.camino("b", "b"), ["b"])

    def test_camino_elige_el_de_menos_saltos(self) -> None:
        g = linea()
        g.agregar_conexion("a", "d")               # atajo
        self.assertEqual(g.camino("a", "d"), ["a", "d"])

    def test_camino_inexistente(self) -> None:
        self.assertIsNone(linea().camino("a", "e"))
        with self.assertRaises(KeyError):
            linea().camino("a", "zzz")

    def test_expuestas_por_anillos(self) -> None:
        g = linea()
        self.assertEqual(g.expuestas("a", 1), [("b",)])
        self.assertEqual(g.expuestas("b", 2), [("a", "c"), ("d",)])
        self.assertEqual(g.expuestas("a", 10), [("b",), ("c",), ("d",)])   # no inventa anillos vacios
        self.assertEqual(g.expuestas("e", 3), [])                           # zona aislada: no se contagia

    def test_distancias_con_limite(self) -> None:
        g = linea()
        self.assertEqual(g.distancias("a"), {"a": 0, "b": 1, "c": 2, "d": 3})
        self.assertEqual(g.distancias("a", 1), {"a": 0, "b": 1})


class CiudadDeEjemploTest(unittest.TestCase):
    def setUp(self) -> None:
        from post_truth.config import RUTA_GRAFO_CIUDAD
        self.g = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    def test_tiene_las_cinco_zonas_y_es_conexa(self) -> None:
        self.assertEqual({z.id for z in self.g.zonas()}, {"colegio", "barrio", "parque", "plaza", "alcaldia"})
        self.assertEqual(len(self.g.distancias(self.g.zona_inicial)), 5)

    def test_la_plaza_es_el_centro(self) -> None:
        self.assertEqual(len(self.g.vecinos("plaza")), 4)
        self.assertEqual(self.g.camino("colegio", "alcaldia"), ["colegio", "plaza", "alcaldia"])

    def test_un_rumor_en_el_colegio_tarda_dos_rondas_en_llegar_a_la_alcaldia(self) -> None:
        anillos = self.g.expuestas("colegio", 3)
        self.assertEqual(len(anillos), 2)
        self.assertIn("alcaldia", anillos[1])


if __name__ == "__main__":
    unittest.main()
