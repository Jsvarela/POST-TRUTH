"""Integracion: mapa ponderado, viajes con energia, evidencia por zona y respaldo de Verificar/Reportar."""
import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, PROPAGACION
from post_truth.models.pistas import ENERGIA_POR_NOTICIA
from post_truth.pygame_app import App
from post_truth.views.escena_view import RECT_MAPA, RECT_TARJETA
from post_truth.views.mapa_view import _posiciones
from post_truth.views.tarjeta_civitas_view import _layout

TECLAS_ZONA = {"colegio": pygame.K_q, "barrio": pygame.K_w, "parque": pygame.K_e, "plaza": pygame.K_r, "alcaldia": pygame.K_t}


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def clic(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


def mover_mouse(app: App, pos: tuple[int, int]) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))


class ViajesEnEscenaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.app.intro_vista = True

    def tearDown(self) -> None:
        pygame.quit()

    def _escena(self, evento: str = "colegio-cerrado", semilla: int = 11, rol_tecla: int = pygame.K_1):
        escena = self.app.estados._estados["escena"]
        escena.rng = random.Random(semilla)
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, rol_tecla)
        tecla(self.app, pygame.K_2)
        escena.indice = next(i for i, a in enumerate(escena.arboles) if a.event.event_id == evento)
        escena._cargar_evento()
        return escena

    def _ir(self, escena, zona: str) -> None:
        clic(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)[zona])

    def _decidir(self, escena, tipo: str) -> None:
        i = next(i for i, n in enumerate(escena.arbol.root.children) if n.tipo == tipo)
        tecla(self.app, [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4][i])

    def _terminar_propagacion(self, escena) -> None:
        if escena.fase == PROPAGACION:
            tecla(self.app, pygame.K_RETURN)
            self.app.estados.update(0.016)
            tecla(self.app, pygame.K_RETURN)

    # --- el mapa de lugares ----------------------------------------------------------------
    def test_el_jugador_empieza_en_la_plaza_con_toda_la_energia(self) -> None:
        escena = self._escena()
        self.assertEqual(escena.zona, "plaza")
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)
        self.assertEqual(escena.investigacion.lugares_pendientes(), {"colegio", "alcaldia", "barrio"})

    def test_ya_no_hay_rumores_rondas_ni_zonas_infectadas(self) -> None:
        escena = self._escena()
        for atributo in ("rumores", "ronda", "_pasar_ronda", "_desmentir", "_mover", "_puede"):
            self.assertFalse(hasattr(escena, atributo), atributo)
        estado = escena._estado_mapa()
        for campo in ("infectadas", "en_riesgo", "zona_noticia", "alcanzables"):
            self.assertFalse(hasattr(estado, campo), campo)

    def test_todas_las_acciones_estan_siempre_disponibles_sin_importar_donde_se_este(self) -> None:
        escena = self._escena()
        for zona in ("plaza", "alcaldia"):
            escena.zona = zona
            escena._construir_botones()
            self.assertTrue(all(b.habilitado for b in escena.botones))
            self.assertFalse(any("(ir a" in b.texto for b in escena.botones))

    # --- viajar ----------------------------------------------------------------------------
    def test_viajar_con_clic_cuesta_la_distancia_y_revela_la_evidencia_del_lugar(self) -> None:
        escena = self._escena()
        self._ir(escena, "colegio")
        self.assertEqual(escena.zona, "colegio")
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 2)       # Plaza -> Colegio = 2
        self.assertTrue(escena.investigacion.esta_descubierta("testigo-directora"))
        self.assertIn("directora", escena.dialogo.texto)
        self.assertIn("costo 2", escena.dialogo.texto)
        self.assertEqual(escena.fase, DECIDIENDO)

    def test_viajar_con_las_letras_q_w_e_r_t(self) -> None:
        escena = self._escena()
        tecla(self.app, TECLAS_ZONA["alcaldia"])
        self.assertEqual(escena.zona, "alcaldia")
        self.assertTrue(escena.investigacion.esta_descubierta("acta-del-consejo"))
        tecla(self.app, TECLAS_ZONA["alcaldia"])                                       # ya esta ahi: no pasa nada
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 2)

    def test_se_puede_ir_a_cualquier_zona_no_solo_a_las_vecinas(self) -> None:
        escena = self._escena()
        escena.zona = "colegio"
        self._ir(escena, "alcaldia")                           # Colegio y Alcaldia no son vecinas: Colegio - Plaza - Alcaldia
        self.assertEqual(escena.zona, "alcaldia")
        self.assertEqual(escena.ruta_vista, ("colegio", "plaza", "alcaldia"))
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 4)

    def test_el_costo_es_el_del_camino_mas_corto_no_el_de_menos_saltos(self) -> None:
        """Barrio -> Plaza: la via directa (1 salto) cuesta 3; por el Parque (2 saltos) cuesta 2."""
        escena = self._escena()
        escena.zona = "barrio"
        self._ir(escena, "plaza")
        self.assertEqual(escena.ruta_vista, ("barrio", "parque", "plaza"))
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 2)

    def test_sin_energia_suficiente_no_se_mueve_ni_se_cobra(self) -> None:
        escena = self._escena()
        escena.investigacion.energia = 1
        self._ir(escena, "colegio")                            # cuesta 2
        self.assertEqual((escena.zona, escena.investigacion.energia), ("plaza", 1))
        self.assertIn("No te alcanza la energia", escena.dialogo.texto)
        self.assertEqual(escena.investigacion.descubiertas, [])

    def test_un_viaje_largo_se_come_casi_toda_la_energia_y_obliga_a_elegir(self) -> None:
        escena = self._escena()
        escena.zona = "alcaldia"
        self._ir(escena, "barrio")                             # costo 4 de 5
        self.assertEqual(escena.investigacion.energia, 1)
        self.assertTrue(escena.investigacion.esta_descubierta("testigo-vecina"))
        tecla(self.app, pygame.K_a)                            # y aun alcanza para 1 pista barata de la tarjeta
        self.assertEqual(escena.investigacion.energia, 0)

    def test_una_zona_sin_evidencia_de_la_noticia_no_revela_nada(self) -> None:
        escena = self._escena()
        self._ir(escena, "parque")
        self.assertEqual(escena.zona, "parque")
        self.assertEqual(escena.investigacion.descubiertas, [])
        self.assertIn("Aqui no hay nada", escena.dialogo.texto)

    def test_volver_a_un_lugar_ya_revisado_no_repite_la_evidencia(self) -> None:
        escena = self._escena()
        self._ir(escena, "colegio")                    # 2 (revela al testigo de la directora)
        self._ir(escena, "barrio")                     # 1 (revela a la vecina)
        self._ir(escena, "colegio")                    # 1 (vuelve: ya estaba revisado)
        self.assertEqual(escena.investigacion.descubiertas, ["testigo-directora", "testigo-vecina"])
        self.assertIn("Ya habias revisado", escena.dialogo.texto)
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA - 4)

    def test_la_ruta_bajo_el_mouse_se_muestra_con_su_costo_sin_viajar(self) -> None:
        escena = self._escena()
        destino = _posiciones(escena._estado_mapa(), RECT_MAPA)["alcaldia"]
        mover_mouse(self.app, destino)
        estado = escena._estado_mapa()
        self.assertEqual(estado.ruta, ("plaza", "alcaldia"))
        self.assertEqual(estado.costo_ruta, 2)
        self.assertEqual(estado.hover, "alcaldia")
        self.assertEqual((escena.zona, escena.investigacion.energia), ("plaza", ENERGIA_POR_NOTICIA))
        mover_mouse(self.app, (5, 5))
        self.assertEqual(escena._estado_mapa().ruta, ())

    def test_el_mapa_marca_las_zonas_con_evidencia_pendiente_y_las_revisadas(self) -> None:
        escena = self._escena()
        self.assertEqual(escena._estado_mapa().pendientes, {"colegio", "alcaldia", "barrio"})
        self._ir(escena, "colegio")
        estado = escena._estado_mapa()
        self.assertEqual(estado.pendientes, {"alcaldia", "barrio"})
        self.assertEqual(estado.revisadas, {"colegio"})

    def test_el_mapa_informa_los_costos_desde_donde_estas_y_la_energia(self) -> None:
        escena = self._escena()
        estado = escena._estado_mapa()
        self.assertEqual(estado.costos, {"plaza": 0, "parque": 1, "colegio": 2, "barrio": 2, "alcaldia": 2})
        self.assertEqual(estado.energia, ENERGIA_POR_NOTICIA)

    def test_la_posicion_se_mantiene_entre_publicaciones_y_la_energia_se_recarga(self) -> None:
        escena = self._escena("colegio-cerrado")
        orden = ["colegio-cerrado", "parques-cerrados"]              # la que sigue a colegio-cerrado: parques-cerrados
        escena.arboles.sort(key=lambda a: orden.index(a.event.event_id) if a.event.event_id in orden else 99)
        escena.indice = 0
        escena._cargar_evento()
        self._ir(escena, "alcaldia")
        self._decidir(escena, "ignorar")
        self._terminar_propagacion(escena)
        tecla(self.app, pygame.K_RETURN)                       # siguiente publicacion
        self.assertEqual(escena.arbol.event.event_id, "parques-cerrados")
        self.assertEqual(escena.zona, "alcaldia")              # el jugador sigue donde se quedo
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)
        self.assertEqual(escena.ruta_vista, ())
        # ...y como esa noticia dejo evidencia en la Alcaldia, se revela sola y sin gastar nada
        self.assertTrue(escena.investigacion.esta_descubierta("registro-de-decretos"))
        self.assertEqual(escena.investigacion.energia, ENERGIA_POR_NOTICIA)

    def test_viajar_no_cambia_los_indicadores(self) -> None:
        escena = self._escena()
        antes = escena.ciudad.as_display_rows()
        self._ir(escena, "colegio")
        self._ir(escena, "alcaldia")
        self.assertEqual(escena.ciudad.as_display_rows(), antes)

    def test_fuera_de_la_fase_de_decidir_no_se_viaja(self) -> None:
        escena = self._escena()
        self._decidir(escena, "ignorar")
        self.assertEqual(escena.fase, CONSECUENCIA)
        self._ir(escena, "colegio")
        tecla(self.app, TECLAS_ZONA["colegio"])
        self.assertEqual(escena.zona, "plaza")

    # --- Verificar y Reportar segun el respaldo ----------------------------------------------
    def _verificar(self, preparar) -> int:
        """verified_information que deja Verificar en colegio-cerrado (la accion base da 12) con el respaldo preparado."""
        self.tearDown()
        self.setUp()
        escena = self._escena()
        preparar(escena)
        self._decidir(escena, "verificar")
        self._terminar_propagacion(escena)
        self.assertEqual(escena.fase, CONSECUENCIA)
        return escena.impacto.verified_information

    def test_verificar_rinde_50_75_o_100_segun_el_respaldo(self) -> None:
        nada = self._verificar(lambda e: None)
        tarjeta = self._verificar(lambda e: tecla(self.app, pygame.K_a))             # pista de la tarjeta
        campo = self._verificar(lambda e: self._ir(e, "colegio"))                   # evidencia de campo
        self.assertEqual((nada, tarjeta, campo), (6, 9, 12))

    def test_verificar_funciona_sin_ir_a_ningun_lugar_pero_a_medias(self) -> None:
        escena = self._escena()
        self._decidir(escena, "verificar")
        self.assertIn(escena.fase, (PROPAGACION, CONSECUENCIA))
        self._terminar_propagacion(escena)
        self.assertIn("50%", escena.dialogo.texto)

    def test_reportar_sin_pruebas_se_rechaza_sin_animacion_y_resta_confianza(self) -> None:
        escena = self._escena()
        grafo_antes = escena.grafo.to_dict()
        confianza = escena.ciudad.trust
        self._decidir(escena, "reportar")
        self.assertEqual(escena.fase, CONSECUENCIA)               # no hay propagacion que animar
        self.assertEqual(escena.grafo.to_dict(), grafo_antes)      # y el grafo no cambia
        self.assertLess(escena.ciudad.trust, confianza)
        self.assertIn("rechazado", escena.dialogo.texto)

    def test_reportar_con_una_pista_de_la_tarjeta_limita_pero_no_corta(self) -> None:
        escena = self._escena()
        tecla(self.app, pygame.K_a)                                # "cuenta sospechosa": apunta a falsa
        self._decidir(escena, "reportar")
        self.assertEqual(escena.fase, PROPAGACION)
        sim = escena.animacion.sim
        self.assertEqual(sim.aristas_cortadas, ())
        self.assertGreater(len(sim.aristas_debilitadas), 0)
        self.assertNotEqual(escena.grafo.vecinos(sim.autor), [])

    def test_reportar_con_evidencia_de_campo_corta_las_conexiones_del_autor(self) -> None:
        escena = self._escena()
        self._ir(escena, "colegio")
        self._decidir(escena, "reportar")
        self.assertEqual(escena.fase, PROPAGACION)
        sim = escena.animacion.sim
        self.assertGreater(len(sim.aristas_cortadas), 0)
        self.assertEqual(escena.grafo.vecinos(sim.autor), [])
        self._terminar_propagacion(escena)
        self.assertIn("aceptado", escena.dialogo.texto)

    def test_el_respaldo_para_reportar_una_noticia_verdadera_es_siempre_cero(self) -> None:
        """Una noticia verdadera nunca tiene pruebas de falsedad: un reporte suyo siempre seria rechazado,
        aunque se haya descubierto TODO; verificar, en cambio, si se apoya en esa evidencia."""
        escena = self._escena("campana-convivencia")
        inv = escena.investigacion
        inv.energia_max = inv.energia = 99
        for pista in inv.pistas:
            inv.investigar(pista.id)
        for evidencia in inv.evidencias:
            inv.revelar_evidencia(evidencia.lugar)
        self.assertEqual(inv.respaldo("reportar"), 0)
        self.assertEqual(inv.respaldo("verificar"), 2)

    def test_los_beneficios_se_atenuan_pero_los_perjuicios_no(self) -> None:
        """Reportar sin pruebas: no recibe ningun beneficio, pero la perdida del reporte infundado se conserva."""
        escena = self._escena()
        self._decidir(escena, "reportar")
        for campo in ("verified_information", "coexistence", "digital_wellbeing"):
            self.assertLessEqual(getattr(escena.impacto, campo), 0, campo)
        self.assertLess(escena.impacto.trust, 0)

    def test_dibuja_el_mapa_nuevo_en_todos_los_temas_y_estados(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            escena = self._escena()
            for zona in ("colegio", "barrio", "parque", "plaza", "alcaldia"):
                mover_mouse(self.app, _posiciones(escena._estado_mapa(), RECT_MAPA)[zona])
                self.app.estados.draw(self.app.pantalla)
                self._ir(escena, zona)
                self.app.estados.draw(self.app.pantalla)
            self.app.estados.cambiar("menu")


if __name__ == "__main__":
    unittest.main()
