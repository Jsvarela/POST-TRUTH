"""Integracion: zonas, movimiento, rondas y rumores dentro de la escena."""
import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, PROPAGACION
from post_truth.pygame_app import App
from post_truth.views.escena_view import RECT_MAPA
from post_truth.views.mapa_view import _posiciones

K = pygame


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def clic(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


class ZonasEnEscenaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()

    def tearDown(self) -> None:
        pygame.quit()

    def _escena(self, evento: str, zona: str | None = None, rol_tecla: int = pygame.K_1):
        """Entra a la escena con `evento` primero; el jugador empieza en la zona inicial (plaza)
        salvo que se pida otra."""
        escena = self.app.estados._estados["escena"]
        escena.rng = random.Random(11)
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, rol_tecla)
        tecla(self.app, pygame.K_2)
        escena.indice = next(i for i, a in enumerate(escena.arboles) if a.event.event_id == evento)
        escena._cargar_evento()
        if zona:
            escena.zona = zona
            escena._construir_botones()
        return escena

    def _decidir(self, escena, tipo: str) -> None:
        i = next(i for i, n in enumerate(escena.arbol.root.children) if n.tipo == tipo)
        tecla(self.app, [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4][i])
        if escena.fase == PROPAGACION:           # salta la animacion del grafo social
            tecla(self.app, pygame.K_RETURN)
            self.app.estados.update(0.016)
            tecla(self.app, pygame.K_RETURN)

    # --- noticia en una zona y movimiento ---------------------------------------------------
    def test_el_jugador_empieza_en_la_zona_inicial_y_la_noticia_tiene_zona(self) -> None:
        escena = self._escena("colegio-cerrado")
        self.assertEqual(escena.zona, "plaza")
        self.assertEqual(escena.arbol.event.zone, "colegio")

    def test_verificar_y_reportar_exigen_estar_en_la_zona_de_la_noticia(self) -> None:
        escena = self._escena("colegio-cerrado")          # el jugador esta en la plaza
        estado = {b.texto.split(". ", 1)[1].split(" (")[0]: b.habilitado for b in escena.botones}
        self.assertEqual(estado, {"Compartir": True, "Verificar": False, "Ignorar": True, "Reportar": False})
        tecla(self.app, pygame.K_2)                        # intentar Verificar desde lejos
        self.assertEqual(escena.fase, DECIDIENDO)
        self.assertEqual(escena.ciudad.verified_information, 55)

    def test_mover_con_clic_en_el_mapa_cuesta_una_ronda(self) -> None:
        escena = self._escena("colegio-cerrado")
        objetivo = _posiciones(escena._estado_mapa(), RECT_MAPA)["colegio"]
        clic(self.app, objetivo)
        self.assertEqual(escena.zona, "colegio")
        self.assertEqual(escena.ronda, 1)

    def test_mover_con_teclado(self) -> None:
        escena = self._escena("colegio-cerrado")
        primero = escena.mapa.vecinos("plaza")[0]
        tecla(self.app, pygame.K_q)
        self.assertEqual(escena.zona, primero)

    def test_solo_se_puede_ir_a_zonas_conectadas(self) -> None:
        escena = self._escena("colegio-cerrado", zona="colegio")
        clic(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)["alcaldia"])   # no es vecina del colegio
        self.assertEqual(escena.zona, "colegio")
        self.assertEqual(escena.ronda, 0)
        clic(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)["colegio"])    # la zona actual tampoco
        self.assertEqual(escena.ronda, 0)

    def test_llegar_a_la_zona_habilita_verificar_y_reportar(self) -> None:
        escena = self._escena("colegio-cerrado")
        clic(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)["colegio"])
        self.assertTrue(all(b.habilitado for b in escena.botones))
        self._decidir(escena, "verificar")
        self.assertEqual(escena.fase, CONSECUENCIA)

    # --- rumores ----------------------------------------------------------------------------
    def test_la_noticia_falsa_es_un_rumor_oculto_hasta_que_corre(self) -> None:
        escena = self._escena("colegio-cerrado")
        self.assertIsNotNone(escena.rumores.rumor("colegio-cerrado"))
        self.assertEqual(escena.rumores.zonas_infectadas(), set())   # no delata que es falsa
        tecla(self.app, pygame.K_q)                                   # una ronda
        self.assertGreater(len(escena.rumores.zonas_infectadas()), 1)

    def test_la_noticia_verdadera_no_genera_rumor(self) -> None:
        escena = self._escena("propuesta-transporte")
        self.assertIsNone(escena.rumores.rumor("propuesta-transporte"))
        tecla(self.app, pygame.K_q)
        self.assertEqual(escena.rumores.zonas_infectadas(), set())

    def test_el_rumor_sin_atender_se_expande_y_penaliza(self) -> None:
        escena = self._escena("colegio-cerrado", zona="colegio")
        antes = escena.ciudad.misinformation
        self._decidir(escena, "ignorar")
        rumor = escena.rumores.rumor("colegio-cerrado")
        self.assertGreaterEqual(len(rumor.zonas), 3)                  # colegio + sus vecinas
        arbol = escena.arbol.accumulated_impact(
            next(n.node_id for n in escena.arbol.root.children if n.tipo == "ignorar"))
        self.assertGreater(escena.impacto.misinformation, arbol.misinformation)   # el rumor cobro lo suyo
        self.assertGreater(escena.ciudad.misinformation, antes)

    def test_verificar_en_la_zona_elimina_el_rumor(self) -> None:
        escena = self._escena("colegio-cerrado", zona="colegio")
        self._decidir(escena, "verificar")
        self.assertIsNone(escena.rumores.rumor("colegio-cerrado"))
        self.assertEqual(escena.rumores.zonas_infectadas(), set())

    def test_reportar_en_la_zona_elimina_el_rumor(self) -> None:
        escena = self._escena("colegio-cerrado", zona="colegio")
        self._decidir(escena, "reportar")
        self.assertIsNone(escena.rumores.rumor("colegio-cerrado"))

    def test_compartir_una_falsa_extiende_el_rumor(self) -> None:
        escena = self._escena("colegio-cerrado")                      # se comparte desde la plaza
        self._decidir(escena, "compartir")
        self.assertGreaterEqual(len(escena.rumores.rumor("colegio-cerrado").zonas), 4)

    def test_moverse_deja_que_el_rumor_avance_aunque_no_decidas(self) -> None:
        escena = self._escena("colegio-cerrado")
        tecla(self.app, pygame.K_q)
        tecla(self.app, pygame.K_q)
        self.assertEqual(escena.ronda, 2)
        self.assertEqual(escena.fase, DECIDIENDO)                     # la noticia sigue esperando
        self.assertEqual(len(escena.rumores.rumor("colegio-cerrado").zonas), 5)

    # --- desmentir --------------------------------------------------------------------------
    def test_desmentir_aparece_solo_en_una_zona_con_un_rumor_viejo(self) -> None:
        escena = self._escena("propuesta-transporte")                 # noticia verdadera en la plaza
        self.assertFalse(any("Desmentir" in b.texto for b in escena.botones))
        escena.rumores.nacer("colegio-cerrado", "colegio")
        escena.rumores.avanzar_ronda()                                # ya ocupa la plaza y es visible
        escena._construir_botones()
        self.assertTrue(any("Desmentir" in b.texto for b in escena.botones))

    def test_desmentir_elimina_el_rumor_da_premio_y_cuesta_una_ronda(self) -> None:
        escena = self._escena("propuesta-transporte")
        escena.rumores.nacer("colegio-cerrado", "colegio")
        escena.rumores.avanzar_ronda()
        escena._construir_botones()
        boton = next(b for b in escena.botones if "Desmentir" in b.texto)
        antes, ronda = escena.ciudad.trust, escena.ronda
        tecla(self.app, boton.atajo)
        self.assertIsNone(escena.rumores.rumor("colegio-cerrado"))
        self.assertGreater(escena.ciudad.trust, antes)
        self.assertEqual(escena.ronda, ronda + 1)
        self.assertEqual(escena.fase, DECIDIENDO)                     # la noticia actual sigue pendiente
        self.assertFalse(any("Desmentir" in b.texto for b in escena.botones))

    def test_no_se_puede_desmentir_la_noticia_que_se_esta_decidiendo(self) -> None:
        escena = self._escena("colegio-cerrado", zona="colegio")
        tecla(self.app, pygame.K_q)                                   # el rumor ya corre y ocupa varias zonas
        escena.zona = "colegio"
        escena._construir_botones()
        self.assertFalse(any("Desmentir" in b.texto for b in escena.botones))

    # --- ciclo de la partida ----------------------------------------------------------------
    def test_iniciar_otra_partida_restaura_ciudad_y_rumores(self) -> None:
        escena = self._escena("colegio-cerrado")
        tecla(self.app, pygame.K_q)
        self.app.estados.cambiar("menu")
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, pygame.K_1)
        tecla(self.app, pygame.K_2)
        self.assertEqual(escena.zona, "plaza")
        self.assertEqual(escena.ronda, 0)
        self.assertEqual(escena.rumores.zonas_infectadas(), set())

    def test_dibuja_en_todos_los_temas_con_rumores_y_cada_zona(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            escena = self._escena("colegio-cerrado")
            for zona in [z.id for z in escena.mapa.zonas()]:
                escena.zona = zona
                escena._construir_botones()
                self.app.estados.update(0.5)
                self.app.estados.draw(self.app.pantalla)
            tecla(self.app, pygame.K_q)
            self._decidir(escena, "ignorar")
            self.app.estados.draw(self.app.pantalla)
            self.app.estados.cambiar("menu")


if __name__ == "__main__":
    unittest.main()
