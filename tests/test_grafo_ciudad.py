import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_GRAFO_CIUDAD
from post_truth.structures.grafo_ciudad import GrafoCiudad, Ruta, Zona


def demo() -> GrafoCiudad:
    """a -1- b -1- c -2- d, atajo a -5- c, y e aislada."""
    g = GrafoCiudad()
    for id in "abcde":
        g.agregar_zona(Zona(id, id.upper()))
    for x, y, d in (("a", "b", 1), ("b", "c", 1), ("c", "d", 2), ("a", "c", 5)):
        g.agregar_conexion(x, y, d)
    return g


class EstructuraTest(unittest.TestCase):
    def test_conexiones_son_no_dirigidas_y_guardan_su_distancia(self) -> None:
        g = demo()
        self.assertEqual(g.vecinos("b"), ["a", "c"])
        self.assertEqual((g.distancia("a", "b"), g.distancia("b", "a")), (1, 1))
        self.assertEqual(g.distancia("a", "c"), 5)
        self.assertIsNone(g.distancia("a", "d"))               # no hay via directa
        self.assertEqual(sorted(g.conexiones()), sorted([("a", "b", 1), ("b", "c", 1), ("c", "d", 2), ("a", "c", 5)]))

    def test_duplicados_lazos_y_zonas_inexistentes(self) -> None:
        g = demo()
        with self.assertRaises(ValueError):
            g.agregar_zona(Zona("a", "otra"))
        with self.assertRaises(ValueError):
            g.agregar_conexion("a", "b", 1)
        with self.assertRaises(ValueError):
            g.agregar_conexion("b", "a", 3)                    # misma conexion, otro orden
        with self.assertRaises(ValueError):
            g.agregar_conexion("a", "a", 1)
        with self.assertRaises(KeyError):
            g.agregar_conexion("a", "zzz", 1)

    def test_la_distancia_debe_ser_un_entero_positivo(self) -> None:
        g = demo()
        for malo in (0, -1, 1.5, "2", None, True):
            with self.assertRaises(ValueError, msg=repr(malo)):
                g.agregar_conexion("a", "e", malo)             # type: ignore[arg-type]
        self.assertIsNone(g.distancia("a", "e"))                # ninguna se agrego

    def test_eliminar_conexion_y_zona(self) -> None:
        g = demo()
        self.assertTrue(g.eliminar_conexion("a", "c"))
        self.assertFalse(g.eliminar_conexion("a", "c"))
        g.eliminar_zona("b")
        self.assertNotIn("b", g)
        self.assertEqual(g.vecinos("a"), [])
        self.assertEqual(g.vecinos("c"), ["d"])
        with self.assertRaises(KeyError):
            g.vecinos("b")

    def test_roundtrip_dict_y_json(self) -> None:
        g = demo()
        g.zona_inicial = "c"
        copia = GrafoCiudad.from_dict(json.loads(json.dumps(g.to_dict())))
        self.assertEqual(copia.to_dict(), g.to_dict())
        self.assertEqual(copia.distancia("c", "d"), 2)

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.structures.grafo_ciudad as modulo
        self.assertNotIn("pygame", vars(modulo))


class DijkstraTest(unittest.TestCase):
    def test_elige_el_camino_de_menor_costo_no_el_de_menos_saltos(self) -> None:
        g = demo()
        r = g.ruta("a", "c")
        self.assertEqual(r, Ruta(("a", "b", "c"), 2))           # 2 saltos y costo 2: gana al directo (1 salto, costo 5)
        self.assertEqual(g.saltos("a")["c"], 1)                  # BFS, en cambio, diria "1 salto"
        self.assertLess(r.costo, g.distancia("a", "c"))

    def test_ruta_costo_y_tramos(self) -> None:
        r = demo().ruta("a", "d")
        self.assertEqual(r.zonas, ("a", "b", "c", "d"))
        self.assertEqual(r.costo, 4)
        self.assertEqual(r.tramos, [("a", "b"), ("b", "c"), ("c", "d")])

    def test_ruta_a_si_misma_cuesta_cero(self) -> None:
        self.assertEqual(demo().ruta("b", "b"), Ruta(("b",), 0))

    def test_sin_ruta_devuelve_none(self) -> None:
        g = demo()
        self.assertIsNone(g.ruta("a", "e"))
        self.assertIsNone(g.ruta("e", "a"))
        self.assertNotIn("e", g.costos_desde("a"))
        with self.assertRaises(KeyError):
            g.ruta("a", "zzz")
        with self.assertRaises(KeyError):
            g.ruta("zzz", "a")

    def test_costos_desde_a_todas_las_zonas_alcanzables(self) -> None:
        self.assertEqual(demo().costos_desde("a"), {"a": 0, "b": 1, "c": 2, "d": 4})

    def test_es_simetrica(self) -> None:
        g = demo()
        for x, y in itertools.permutations("abcd", 2):
            self.assertEqual(g.ruta(x, y).costo, g.ruta(y, x).costo)
            self.assertEqual(g.ruta(x, y).zonas, tuple(reversed(g.ruta(y, x).zonas)))

    def test_empate_se_resuelve_siempre_igual(self) -> None:
        g = GrafoCiudad()
        for id in "abcd":
            g.agregar_zona(Zona(id, id))
        for x, y in (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")):
            g.agregar_conexion(x, y, 1)
        for _ in range(5):
            self.assertEqual(g.ruta("a", "d"), Ruta(("a", "b", "d"), 2))

    def test_el_costo_de_la_ruta_es_la_suma_de_sus_tramos(self) -> None:
        g = demo()
        for x, y in itertools.permutations("abcd", 2):
            r = g.ruta(x, y)
            self.assertEqual(r.costo, sum(g.distancia(a, b) for a, b in r.tramos))

    def test_coincide_con_floyd_warshall_en_grafos_al_azar(self) -> None:
        """Comparacion con una solucion independiente (Floyd-Warshall, O(V^3)) en 60 grafos aleatorios."""
        for semilla in range(60):
            rng = random.Random(semilla)
            n = rng.randint(2, 8)
            g = GrafoCiudad()
            ids = [f"z{i}" for i in range(n)]
            for id in ids:
                g.agregar_zona(Zona(id, id))
            INF = float("inf")
            m = {(a, b): (0 if a == b else INF) for a in ids for b in ids}
            for a, b in itertools.combinations(ids, 2):
                if rng.random() < 0.45:
                    d = rng.randint(1, 6)
                    g.agregar_conexion(a, b, d)
                    m[(a, b)] = m[(b, a)] = d
            for k, i, j in itertools.product(ids, ids, ids):
                m[(i, j)] = min(m[(i, j)], m[(i, k)] + m[(k, j)])
            for a, b in itertools.product(ids, ids):
                ruta = g.ruta(a, b)
                if m[(a, b)] == INF:
                    self.assertIsNone(ruta, (semilla, a, b))
                else:
                    self.assertEqual(ruta.costo, m[(a, b)], (semilla, a, b))


class ConectividadTest(unittest.TestCase):
    def test_bfs_cuenta_saltos_y_es_conexo(self) -> None:
        g = demo()
        self.assertEqual(g.saltos("a"), {"a": 0, "b": 1, "c": 1, "d": 2})
        self.assertFalse(g.es_conexo())                          # e esta aislada
        g.eliminar_zona("e")
        self.assertTrue(g.es_conexo())
        g.eliminar_conexion("c", "d")
        self.assertFalse(g.es_conexo())

    def test_cargar_exige_un_mapa_conexo(self) -> None:
        g = demo()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "mapa.json"
            ruta.write_text(json.dumps(g.to_dict()), encoding="utf-8")
            with self.assertRaises(ValueError):
                GrafoCiudad.cargar(ruta)
            self.assertFalse(GrafoCiudad.cargar(ruta, exigir_conexo=False).es_conexo())


class CiudadDeEjemploTest(unittest.TestCase):
    def setUp(self) -> None:
        self.g = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    def test_tiene_las_cinco_zonas_con_distancias(self) -> None:
        self.assertEqual({z.id for z in self.g.zonas()}, {"colegio", "barrio", "parque", "plaza", "alcaldia"})
        self.assertEqual(len(self.g.conexiones()), 6)
        self.assertTrue(self.g.es_conexo())
        self.assertEqual(self.g.zona_inicial, "plaza")
        for _, _, d in self.g.conexiones():
            self.assertGreaterEqual(d, 1)

    def test_el_mapa_distingue_dijkstra_de_bfs(self) -> None:
        """Barrio -> Plaza: la via directa (1 salto) cuesta 3; por el Parque (2 saltos) cuesta 2."""
        self.assertEqual(self.g.saltos("barrio")["plaza"], 1)
        r = self.g.ruta("barrio", "plaza")
        self.assertEqual(r, Ruta(("barrio", "parque", "plaza"), 2))

    def test_costos_de_viaje_desde_la_plaza(self) -> None:
        self.assertEqual(self.g.costos_desde("plaza"),
                         {"plaza": 0, "parque": 1, "colegio": 2, "barrio": 2, "alcaldia": 2})

    def test_el_viaje_mas_largo_cuesta_cuatro(self) -> None:
        costos = {(a.id, b.id): self.g.ruta(a.id, b.id).costo for a in self.g.zonas() for b in self.g.zonas()}
        self.assertEqual(max(costos.values()), 4)
        self.assertEqual(self.g.ruta("colegio", "alcaldia").zonas, ("colegio", "plaza", "alcaldia"))
        self.assertEqual(self.g.ruta("alcaldia", "barrio").costo, 4)


if __name__ == "__main__":
    unittest.main()
