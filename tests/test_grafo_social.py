import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.models import Role
from post_truth.structures.grafo_social import Ciudadano, GrafoSocial, TipoRelacion


class SiempreActiva:
    """rng que activa todas las aristas (random() < p siempre): propagacion determinista."""
    def random(self) -> float:
        return 0.0


class NuncaActiva:
    def random(self) -> float:
        return 0.999999


def grafo_cadena() -> GrafoSocial:
    """a -> b -> c, y un atajo debil a -> c. d queda aislado."""
    g = GrafoSocial()
    for id, rol in (("a", Role.CITIZEN), ("b", Role.CITIZEN), ("c", Role.CITIZEN), ("d", Role.CITIZEN)):
        g.agregar_vertice(Ciudadano(id, id.upper(), rol))
    g.agregar_arista("a", "b", 0.9)
    g.agregar_arista("b", "c", 0.9)
    g.agregar_arista("a", "c", 0.1)
    return g


class EstructuraTest(unittest.TestCase):
    def test_insertar_y_consultar(self) -> None:
        g = grafo_cadena()
        self.assertEqual({c.id for c in g.vertices()}, {"a", "b", "c", "d"})
        self.assertEqual({a.destino for a in g.vecinos("a")}, {"b", "c"})
        self.assertEqual(g.vecinos("d"), [])

    def test_aristas_son_dirigidas(self) -> None:
        g = grafo_cadena()
        self.assertIsNotNone(g.arista("a", "b"))
        self.assertIsNone(g.arista("b", "a"))

    def test_vertice_duplicado_y_arista_invalida(self) -> None:
        g = grafo_cadena()
        with self.assertRaises(ValueError):
            g.agregar_vertice(Ciudadano("a", "otra", Role.CITIZEN))
        with self.assertRaises(ValueError):
            g.agregar_arista("a", "b", 0.5)       # duplicada
        with self.assertRaises(ValueError):
            g.agregar_arista("a", "a", 0.5)       # lazo
        with self.assertRaises(ValueError):
            g.agregar_arista("d", "a", 0.0)       # peso fuera de rango
        with self.assertRaises(KeyError):
            g.agregar_arista("a", "zzz", 0.5)     # vertice inexistente

    def test_eliminar_arista(self) -> None:
        g = grafo_cadena()
        self.assertTrue(g.eliminar_arista("a", "c"))
        self.assertFalse(g.eliminar_arista("a", "c"))
        self.assertEqual([a.destino for a in g.vecinos("a")], ["b"])

    def test_eliminar_vertice_quita_aristas_entrantes_y_salientes(self) -> None:
        g = grafo_cadena()
        g.eliminar_vertice("b")
        self.assertEqual([a.destino for a in g.vecinos("a")], ["c"])
        self.assertNotIn("b", {c.id for c in g.vertices()})
        self.assertEqual(len(g.aristas()), 1)
        with self.assertRaises(KeyError):
            g.vecinos("b")

    def test_debilitar_y_cortar(self) -> None:
        g = grafo_cadena()
        g.debilitar_salientes("a", 0.5)
        self.assertAlmostEqual(g.arista("a", "b").peso, 0.45)
        self.assertEqual(len(g.cortar_salientes("a")), 2)
        self.assertEqual(g.vecinos("a"), [])

    def test_roundtrip_dict_y_json(self) -> None:
        g = grafo_cadena()
        g.agregar_arista("c", "d", 0.4, TipoRelacion.SEGUIMIENTO)
        copia = GrafoSocial.from_dict(json.loads(json.dumps(g.to_dict())))
        self.assertEqual(copia.to_dict(), g.to_dict())

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.structures.grafo_social as modulo
        self.assertNotIn("pygame", vars(modulo))


class PropagacionTest(unittest.TestCase):
    def test_olas_bfs(self) -> None:
        r = grafo_cadena().propagar("a", es_falsa=True, rng=SiempreActiva())
        # a -> {b, c} en la ola 1 (c se alcanza por el atajo directo); d nunca la recibe
        self.assertEqual(r.olas[0], ("a",))
        self.assertEqual(set(r.olas[1]), {"b", "c"})
        self.assertEqual(r.alcanzados, 2)
        self.assertNotIn("d", r.tiempos)

    def test_nadie_recibe_si_ninguna_arista_se_activa(self) -> None:
        r = grafo_cadena().propagar("a", True, NuncaActiva())
        self.assertEqual(r.alcanzados, 0)
        self.assertEqual(r.olas, (("a",),))

    def test_dijkstra_prefiere_el_camino_rapido_aunque_tenga_mas_saltos(self) -> None:
        r = grafo_cadena().propagar("a", True, SiempreActiva())
        # Directo a->c cuesta 1/0.1 = 10; por b cuesta 1/0.9 + 1/0.9 ~ 2.2: gana el de 2 saltos
        self.assertAlmostEqual(r.tiempos["c"], 2 / 0.9)
        self.assertEqual(r.padres["c"], "a")  # pero BFS lo ubica en la ola 1: por eso hace falta Dijkstra
        self.assertLess(r.tiempos["c"], 1 / 0.1)

    def test_el_influencer_amplifica(self) -> None:
        def alcance(rol: Role) -> int:
            total = 0
            for semilla in range(300):
                g = GrafoSocial()
                g.agregar_vertice(Ciudadano("x", "X", rol))
                for i in range(10):
                    g.agregar_vertice(Ciudadano(f"v{i}", f"V{i}", Role.CITIZEN))
                    g.agregar_arista("x", f"v{i}", 0.5)
                total += g.propagar("x", True, random.Random(semilla)).alcanzados
            return total
        self.assertGreater(alcance(Role.INFLUENCER), alcance(Role.CITIZEN) * 1.2)

    def test_periodista_frena_noticias_falsas_pero_no_las_verdaderas(self) -> None:
        g = GrafoSocial()
        g.agregar_vertice(Ciudadano("a", "A", Role.CITIZEN))
        g.agregar_vertice(Ciudadano("p", "P", Role.JOURNALIST))
        g.agregar_vertice(Ciudadano("z", "Z", Role.CITIZEN))
        g.agregar_arista("a", "p", 0.9)
        g.agregar_arista("p", "z", 0.9)
        falsa = g.propagar("a", True, SiempreActiva())
        self.assertEqual(falsa.alcanzados, 1)          # solo llega al periodista
        self.assertEqual(falsa.frenados, ("p",))
        verdadera = g.propagar("a", False, SiempreActiva())
        self.assertEqual(verdadera.alcanzados, 2)      # el periodista si la difunde

    def test_consecuencias_segun_veracidad(self) -> None:
        g = grafo_cadena()
        falsa = g.propagar("a", True, SiempreActiva()).impacto()
        self.assertGreater(falsa.misinformation, 0)
        self.assertGreater(falsa.conflicts, 0)
        self.assertEqual(falsa.verified_information, 0)
        verdadera = g.propagar("a", False, SiempreActiva()).impacto()
        self.assertGreater(verdadera.verified_information, 0)
        self.assertEqual(verdadera.misinformation, 0)

    def test_misma_semilla_mismo_resultado(self) -> None:
        g = grafo_cadena()
        self.assertEqual(g.propagar("a", True, random.Random(7)).to_dict(),
                         g.propagar("a", True, random.Random(7)).to_dict())

    def test_propagar_desde_vertice_inexistente(self) -> None:
        with self.assertRaises(KeyError):
            grafo_cadena().propagar("nadie", True)


if __name__ == "__main__":
    unittest.main()
