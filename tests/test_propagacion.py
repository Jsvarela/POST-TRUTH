import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_GRAFO_SOCIAL
from post_truth.models import Role
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import COMPARTIR, IGNORAR, REPORTAR, VERIFICAR, simular_decision


def promedio_alcance(tipo: str, es_falsa: bool, rol: Role = Role.CITIZEN, autor: str = "tomas",
                     n: int = 200) -> float:
    total = 0
    for semilla in range(n):
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        g.cambiar_rol("jugador", rol)
        sim = simular_decision(g, tipo, es_falsa, "jugador", autor, random.Random(semilla))
        total += sim.resultado.alcanzados
    return total / n


class SimularDecisionTest(unittest.TestCase):
    def test_ignorar_no_simula(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        self.assertIsNone(simular_decision(g, IGNORAR, True, "jugador", "tomas"))
        self.assertIsNone(simular_decision(g, "otra-cosa", True, "jugador", "tomas"))

    def test_compartir_parte_del_jugador(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        sim = simular_decision(g, COMPARTIR, True, "jugador", "tomas", random.Random(1))
        self.assertEqual(sim.resultado.origen, "jugador")
        self.assertGreater(sim.resultado.alcanzados, 0)

    def test_reportar_elimina_las_aristas_del_autor(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        antes = len(g.vecinos("tomas"))
        sim = simular_decision(g, REPORTAR, True, "jugador", "tomas", random.Random(1))
        self.assertEqual(len(sim.aristas_cortadas), antes)
        self.assertEqual(g.vecinos("tomas"), [])           # el corte es persistente
        self.assertEqual(sim.resultado.alcanzados, 0)      # y la noticia no sale de su autor

    def test_verificar_baja_pesos_y_reduce_el_alcance_de_una_falsa(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        peso_antes = g.arista("tomas", "isabela").peso
        simular_decision(g, VERIFICAR, True, "jugador", "tomas", random.Random(1))
        self.assertLess(g.arista("tomas", "isabela").peso, peso_antes)
        self.assertGreater(promedio_alcance(COMPARTIR, True, autor="tomas"),
                           promedio_alcance(VERIFICAR, True, autor="tomas"))

    def test_verificar_una_verdadera_no_frena(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        peso_antes = g.arista("tomas", "isabela").peso
        sim = simular_decision(g, VERIFICAR, False, "jugador", "tomas", random.Random(1))
        self.assertEqual(g.arista("tomas", "isabela").peso, peso_antes)
        self.assertEqual(sim.aristas_debilitadas, ())

    def test_compartir_alcanza_mas_que_reportar_o_verificar(self) -> None:
        compartir = promedio_alcance(COMPARTIR, True)
        self.assertGreater(compartir, promedio_alcance(VERIFICAR, True))
        self.assertGreater(compartir, promedio_alcance(REPORTAR, True))

    def test_el_rol_del_jugador_cambia_el_alcance_al_compartir(self) -> None:
        self.assertGreater(promedio_alcance(COMPARTIR, True, Role.INFLUENCER),
                           promedio_alcance(COMPARTIR, True, Role.CITIZEN))

    def test_consecuencias_falsa_vs_verdadera(self) -> None:
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        falsa = simular_decision(g, COMPARTIR, True, "jugador", "tomas", random.Random(3)).resultado.impacto()
        g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        verdadera = simular_decision(g, COMPARTIR, False, "jugador", "tomas", random.Random(3)).resultado.impacto()
        self.assertGreater(falsa.misinformation, 0)
        self.assertGreater(verdadera.verified_information, 0)


if __name__ == "__main__":
    unittest.main()
