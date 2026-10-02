"""Integracion: tarjeta de Civitas, pistas clicables, energia y texto de consecuencia en la escena."""
import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, PROPAGACION
from post_truth.models.pistas import ENERGIA_POR_NOTICIA, ZonaTarjeta
from post_truth.pygame_app import App
from post_truth.views.escena_view import RECT_MAPA, RECT_TARJETA
from post_truth.views.mapa_view import _posiciones
from post_truth.views.tarjeta_civitas_view import _layout


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def clic(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


def mover_mouse(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))


class InvestigarEnEscenaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.app.intro_vista = True

    def tearDown(self) -> None:
        pygame.quit()

    def _escena(self, evento: str = "colegio-cerrado", semilla: int = 11):
        escena = self.app.estados._estados["escena"]
        escena.rng = random.Random(semilla)
        escena.eventos_por_partida = None   # estas pruebas usan noticias concretas: se juegan todas
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, pygame.K_1)
        tecla(self.app, pygame.K_2)
        escena.indice = next(i for i, a in enumerate(escena.arboles) if a.event.event_id == evento)
        escena._cargar_evento()
        return escena

    def _zona(self, escena, pista_id: str) -> tuple[int, int]:
        zona = escena.investigacion.pista(pista_id).zona
        return _layout(RECT_TARJETA)[zona].center

    def _terminar_propagacion(self, escena) -> None:
        if escena.fase == PROPAGACION:
            tecla(self.app, pygame.K_RETURN)
            self.app.estados.update(0.016)
            tecla(self.app, pygame.K_RETURN)

    # --- investigar --------------------------------------------------------------------------
    def test_cada_publicacion_empieza_con_la_energia_completa_y_sin_pistas(self) -> None:
        escena = self._escena()
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)
        self.assertEqual(escena.investigacion.descubiertas, [])
        self.assertEqual(len(escena.investigacion.pistas), 5)

    def test_clic_en_una_zona_revela_la_pista_gasta_energia_y_la_dice_en_el_dialogo(self) -> None:
        escena = self._escena()
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))
        self.assertTrue(escena.investigacion.esta_descubierta("cuenta-sospechosa"))
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 1)
        self.assertIn("Cuenta sospechosa", escena.dialogo.texto)
        self.assertIn("2 dias de creada", escena.dialogo.texto)
        self.assertTrue(escena.dialogo.terminado)            # el hallazgo se ve de inmediato, sin esperar
        self.assertEqual(escena.fase, DECIDIENDO)            # y la publicacion sigue esperando la decision

    def test_se_investiga_tambien_con_las_letras_a_s_d_f_g(self) -> None:
        escena = self._escena()
        for i, letra in enumerate((pygame.K_a, pygame.K_s, pygame.K_d)):
            antes = escena.investigacion.energia
            tecla(self.app, letra)
            esperada = escena.investigacion.pistas[i]
            if antes >= esperada.costo:
                self.assertTrue(escena.investigacion.esta_descubierta(esperada.id), esperada.id)

    def test_la_energia_obliga_a_elegir_y_no_cobra_si_no_alcanza(self) -> None:
        escena = self._escena()
        clic(self.app, self._zona(escena, "imagen-reutilizada"))      # cuesta 2
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))       # cuesta 1
        clic(self.app, self._zona(escena, "sin-fuente"))              # cuesta 1
        clic(self.app, self._zona(escena, "comentarios-repetidos"))   # cuesta 1: la energia (5) se acabo
        self.assertEqual(escena.investigacion.energia, 0)
        clic(self.app, self._zona(escena, "hora-normal"))             # ya no alcanza
        self.assertFalse(escena.investigacion.esta_descubierta("hora-normal"))
        self.assertEqual(escena.investigacion.energia, 0)
        self.assertIn("No te queda energia", escena.dialogo.texto)

    def test_releer_una_pista_ya_revisada_es_gratis(self) -> None:
        escena = self._escena()
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))
        energia = escena.investigacion.energia
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))
        self.assertEqual(escena.investigacion.energia, energia)
        self.assertEqual(escena.investigacion.descubiertas, ["cuenta-sospechosa"])
        self.assertIn("2 dias de creada", escena.dialogo.texto)

    def test_investigar_solo_cuesta_energia_no_mueve_al_jugador_ni_cambia_indicadores(self) -> None:
        """Revisar la tarjeta gasta energia y nada mas: ni se viaja, ni se tocan los indicadores."""
        escena = self._escena()
        antes = (escena.ciudad.as_display_rows(), escena.zona, escena.ruta_vista)
        for pista in escena.investigacion.pistas[:3]:
            clic(self.app, self._zona(escena, pista.id))
        self.assertEqual((escena.ciudad.as_display_rows(), escena.zona, escena.ruta_vista), antes)
        self.assertLess(escena.investigacion.energia, ENERGIA_POR_NOTICIA)
        self.assertEqual(escena.investigacion.viaje_gastado, 0)

    def test_una_zona_sin_pista_o_un_clic_fuera_no_hacen_nada(self) -> None:
        escena = self._escena()
        sin_pista = set(ZonaTarjeta) - {p.zona for p in escena.investigacion.pistas}
        self.assertTrue(sin_pista)
        for zona in sin_pista:
            clic(self.app, _layout(RECT_TARJETA)[zona].center)
        clic(self.app, (5, 5))
        self.assertEqual(escena.investigacion.descubiertas, [])
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)

    def test_el_mouse_encima_resalta_la_zona(self) -> None:
        escena = self._escena()
        mover_mouse(self.app, self._zona(escena, "cuenta-sospechosa"))
        self.assertIs(escena._hover, ZonaTarjeta.AUTOR)
        mover_mouse(self.app, (5, 5))
        self.assertIsNone(escena._hover)

    def test_la_energia_y_las_pistas_se_reinician_en_la_siguiente_publicacion(self) -> None:
        escena = self._escena()
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))
        tecla(self.app, pygame.K_3)                              # Ignorar
        self.assertEqual(escena.fase, CONSECUENCIA)
        tecla(self.app, pygame.K_RETURN)                         # siguiente publicacion
        self.assertEqual(escena.fase, DECIDIENDO)
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)
        self.assertEqual(escena.investigacion.descubiertas, [])

    def test_fuera_de_la_fase_de_decidir_no_se_investiga(self) -> None:
        escena = self._escena()
        tecla(self.app, pygame.K_3)                              # Ignorar -> consecuencia
        self.assertEqual(escena.fase, CONSECUENCIA)
        clic(self.app, self._zona(escena, "cuenta-sospechosa"))
        tecla(self.app, pygame.K_a)
        self.assertEqual(escena.investigacion.descubiertas, [])

    def test_el_clic_en_el_mapa_y_en_la_tarjeta_no_se_confunden(self) -> None:
        escena = self._escena()
        self.assertFalse(RECT_TARJETA.colliderect(RECT_MAPA))
        clic(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)["colegio"])
        self.assertEqual(escena.zona, "colegio")                       # el clic del mapa viajo...
        ids_de_tarjeta = {p.id for p in escena.investigacion.pistas}
        self.assertEqual([id for id in escena.investigacion.descubiertas if id in ids_de_tarjeta], [])   # ...sin tocar la tarjeta

    # --- consecuencia segun lo investigado -----------------------------------------------------
    def _consecuencia_de(self, investigar: list[str], tipo: str = "compartir") -> str:
        escena = self._escena()
        for id in investigar:
            clic(self.app, self._zona(escena, id))
        i = next(i for i, n in enumerate(escena.arbol.root.children) if n.tipo == tipo)
        tecla(self.app, [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4][i])
        self._terminar_propagacion(escena)
        self.assertEqual(escena.fase, CONSECUENCIA)
        return escena.dialogo.texto.split("\n")[0]       # la 1.a linea es la consecuencia; la 2.a, el aviso del respaldo

    def test_las_pistas_descubiertas_cambian_el_texto_de_la_consecuencia(self) -> None:
        base = self._consecuencia_de([])
        con_imagen = self._consecuencia_de(["imagen-reutilizada"])
        con_cuenta = self._consecuencia_de(["cuenta-sospechosa"])
        self.assertEqual(len({base, con_imagen, con_cuenta}), 3)
        self.assertIn("2021", con_imagen)
        self.assertIn("Dudabas de la cuenta", con_cuenta)

    def test_sin_investigar_se_usa_el_texto_base_de_la_decision(self) -> None:
        escena = self.app.estados._estados["escena"]
        texto = self._consecuencia_de([])
        compartir = next(n for n in self.app.estados._estados["escena"].arbol.root.children if n.tipo == "compartir")
        self.assertEqual(texto, compartir.description)

    def test_una_pista_neutra_solo_agrega_lo_revisado(self) -> None:
        texto = self._consecuencia_de(["hora-normal"])
        self.assertIn("Habias revisado: hora normal.", texto)

    def test_el_texto_depende_de_la_decision_y_de_las_pistas_juntas(self) -> None:
        compartir = self._consecuencia_de(["imagen-reutilizada"], "compartir")
        ignorar = self._consecuencia_de(["cuenta-sospechosa", "imagen-reutilizada"], "ignorar")
        self.assertNotEqual(compartir, ignorar)
        self.assertIn("Tenias pruebas", ignorar)

    def test_investigar_no_cambia_los_numeros_de_la_decision(self) -> None:
        """Mismo rol, evento, semilla y decision: los indicadores finales son iguales con o sin pistas."""
        def indicadores(investigar: list[str]) -> list:
            self.tearDown()
            self.setUp()
            escena = self._escena()
            for id in investigar:
                clic(self.app, self._zona(escena, id))
            tecla(self.app, pygame.K_3)                  # Ignorar: sin propagacion aleatoria que dependa del orden
            return escena.ciudad.as_display_rows()
        self.assertEqual(indicadores([]), indicadores(["cuenta-sospechosa", "imagen-reutilizada"]))

    def test_dibuja_la_escena_con_la_tarjeta_en_los_3_temas_y_todas_las_noticias(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            for evento in ("colegio-cerrado", "parques-cerrados", "propuesta-transporte", "video-debate-editado",
                           "campana-convivencia"):
                escena = self._escena(evento)
                mover_mouse(self.app, _layout(RECT_TARJETA)[escena.investigacion.pistas[0].zona].center)
                self.app.estados.draw(self.app.pantalla)
                for pista in escena.investigacion.pistas:
                    clic(self.app, _layout(RECT_TARJETA)[pista.zona].center)
                    self.app.estados.draw(self.app.pantalla)
                self.app.estados.cambiar("menu")


if __name__ == "__main__":
    unittest.main()
