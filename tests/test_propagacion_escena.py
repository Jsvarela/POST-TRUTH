"""Integracion: decision en la escena -> propagacion por el grafo social -> consecuencias."""
import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, PROPAGACION
from post_truth.models import Role
from post_truth.pygame_app import App


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


class PropagacionEnEscenaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()

    def tearDown(self) -> None:
        pygame.quit()

    def _escena(self, evento: str, rol_tecla: int = pygame.K_1, semilla: int = 11):
        """Entra a la escena con el evento pedido en primer lugar."""
        escena = self.app.estados._estados["escena"]
        escena.rng = random.Random(semilla)
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, rol_tecla)
        tecla(self.app, pygame.K_2)
        escena.indice = next(i for i, a in enumerate(escena.arboles) if a.event.event_id == evento)
        escena._cargar_evento()
        escena.zona = escena.arbol.event.zone   # el jugador ya esta en el lugar: Verificar/Reportar disponibles
        escena._construir_botones()
        return escena

    def _decidir_tipo(self, escena, tipo: str) -> None:
        i = next(i for i, n in enumerate(escena.arbol.root.children) if n.tipo == tipo)
        tecla(self.app, [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4][i])

    def _reproducir(self, escena) -> list[str]:
        """Avanza la animacion con dt reales de 60 FPS y devuelve las narraciones que se vieron."""
        vistas = [escena.dialogo.texto]
        for _ in range(60 * 30):
            self.app.estados.update(1 / 60)
            self.app.estados.draw(self.app.pantalla)
            if escena.dialogo.texto != vistas[-1]:
                vistas.append(escena.dialogo.texto)
            if escena.botones[0].texto.startswith("Ver consecuencias"):
                return vistas
        self.fail("la animacion no termino")

    def test_compartir_falsa_anima_y_luego_sube_desinformacion(self) -> None:
        escena = self._escena("parques-cerrados")
        antes = escena.ciudad.misinformation
        self._decidir_tipo(escena, "compartir")
        self.assertEqual(escena.fase, PROPAGACION)
        self.assertEqual(escena.ciudad.misinformation, antes)      # aun no hay consecuencias
        narraciones = self._reproducir(escena)
        self.assertGreater(len(narraciones), 2)                    # la caja de dialogo narra las olas
        self.assertTrue(any(t.startswith("Ola 1") for t in narraciones))
        self.assertEqual(escena.fase, PROPAGACION)                 # espera al jugador
        tecla(self.app, pygame.K_RETURN)
        self.assertEqual(escena.fase, CONSECUENCIA)
        self.assertGreater(escena.ciudad.misinformation, antes)
        self.assertIsNotNone(escena.impacto)

    def test_compartir_verdadera_sube_informacion_verificada(self) -> None:
        escena = self._escena("propuesta-transporte")
        antes = escena.ciudad.verified_information
        self._decidir_tipo(escena, "compartir")
        self.assertEqual(escena.animacion.resultado.es_falsa, False)
        self.app.estados.update(60)    # un dt enorme termina la animacion en un solo frame
        tecla(self.app, pygame.K_RETURN)
        self.assertGreater(escena.ciudad.verified_information, antes)

    def test_reportar_corta_las_aristas_del_autor_de_forma_persistente(self) -> None:
        escena = self._escena("colegio-cerrado")
        self._decidir_tipo(escena, "reportar")
        autor = escena.animacion.sim.autor
        self.assertEqual(escena.grafo.vecinos(autor), [])
        self.assertGreater(len(escena.animacion.sim.aristas_cortadas), 0)
        self.assertEqual(escena.animacion.resultado.alcanzados, 0)

    def test_verificar_limita_la_propagacion_de_una_falsa(self) -> None:
        escena = self._escena("colegio-cerrado")
        pesos_antes = {(a.origen, a.destino): a.peso for a in escena.grafo.aristas()}
        self._decidir_tipo(escena, "verificar")
        sim = escena.animacion.sim
        self.assertGreater(len(sim.aristas_debilitadas), 0)
        for o, d in sim.aristas_debilitadas:
            self.assertLess(escena.grafo.arista(o, d).peso, pesos_antes[(o, d)])

    def test_ignorar_no_dispara_propagacion(self) -> None:
        escena = self._escena("colegio-cerrado")
        self._decidir_tipo(escena, "ignorar")
        self.assertEqual(escena.fase, CONSECUENCIA)
        self.assertIsNone(escena.animacion)

    def test_el_corte_persiste_en_la_siguiente_publicacion(self) -> None:
        escena = self._escena("colegio-cerrado")
        self._decidir_tipo(escena, "reportar")
        autor = escena.animacion.sim.autor
        self.app.estados.update(60)
        tecla(self.app, pygame.K_RETURN)   # ver consecuencias
        tecla(self.app, pygame.K_RETURN)   # continuar a la siguiente publicacion
        self.assertEqual(escena.fase, DECIDIENDO)
        self.assertEqual(escena.grafo.vecinos(autor), [])

    def test_el_rol_elegido_es_el_del_vertice_del_jugador(self) -> None:
        escena = self._escena("colegio-cerrado", rol_tecla=pygame.K_3)
        self.assertIs(escena.grafo.vertice("jugador").rol, Role.INFLUENCER)

    def test_reiniciar_la_partida_restaura_el_grafo(self) -> None:
        escena = self._escena("colegio-cerrado")
        self._decidir_tipo(escena, "reportar")
        autor = escena.animacion.sim.autor
        self.app.estados.cambiar("menu")
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, pygame.K_1)
        tecla(self.app, pygame.K_2)
        self.assertNotEqual(escena.grafo.vecinos(autor), [])

    def test_dibuja_la_propagacion_en_todos_los_temas(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            escena = self._escena("parques-cerrados")
            self._decidir_tipo(escena, "compartir")
            self._reproducir(escena)
            self.app.estados.cambiar("menu")


if __name__ == "__main__":
    unittest.main()
