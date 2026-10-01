"""Estado de la introduccion y su lugar en el flujo: Menu -> Intro -> Seleccion -> Escena."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.intro_state import (CARACTERES_POR_SEGUNDO, ENTRANDO, FADE_ENTRADA, FADE_SALIDA,
                                                MANTENIENDO, SALIENDO)
from post_truth.pygame_app import App


def tecla(app: App, k: int) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def clic(app: App, pos: tuple[int, int] = (500, 250)) -> None:
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.estados.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))


class IntroEstadoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.intro = self.app.estados._estados["intro"]

    def tearDown(self) -> None:
        pygame.quit()

    def _estado(self, nombre: str) -> bool:
        return self.app.estados._actual is self.app.estados._estados[nombre]

    def _avanzar_una_lamina(self, entrada: str = "clic") -> None:
        """Avanza hasta cambiar de lamina (o salir de la intro), con dt reales de 60 FPS."""
        i = self.intro.indice
        for _ in range(200):
            if not self._estado("intro") or self.intro.indice != i:
                return
            (clic(self.app) if entrada == "clic" else tecla(self.app, pygame.K_SPACE))
            for f in range(36):                         # ~0.6 s de fotogramas: alcanza para un fundido
                self.app.estados.update(1 / 60)
                if f % 6 == 0:
                    self.app.estados.draw(self.app.pantalla)
        self.fail("la introduccion no avanza")

    # --- flujo -----------------------------------------------------------------------------
    def test_la_primera_vez_enter_lleva_a_la_intro_y_al_terminar_a_la_seleccion(self) -> None:
        self.assertFalse(self.app.intro_vista)
        tecla(self.app, pygame.K_RETURN)
        self.assertTrue(self._estado("intro"))
        total = len(self.intro.intro.laminas)
        for i in range(total):
            self.assertTrue(self._estado("intro"))
            self.assertEqual(self.intro.indice, i)
            self._avanzar_una_lamina()
        self.assertTrue(self._estado("seleccion"))
        self.assertTrue(self.app.intro_vista)

    def test_la_segunda_vez_enter_va_directo_a_la_seleccion(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, pygame.K_ESCAPE)                 # saltar
        self.app.estados.cambiar("menu")
        tecla(self.app, pygame.K_RETURN)
        self.assertTrue(self._estado("seleccion"))

    def test_con_i_se_vuelve_a_ver_desde_el_principio(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        self._avanzar_una_lamina()
        self._avanzar_una_lamina()
        tecla(self.app, pygame.K_ESCAPE)
        self.app.estados.cambiar("menu")
        tecla(self.app, pygame.K_i)
        self.assertTrue(self._estado("intro"))
        self.assertEqual(self.intro.indice, 0)
        self.assertEqual(self.intro.fase, ENTRANDO)

    def test_esc_salta_la_intro_completa_desde_cualquier_lamina(self) -> None:
        for lamina in range(len(self.intro.intro.laminas)):
            self.app.intro_vista = False
            self.app.estados.cambiar("menu")
            tecla(self.app, pygame.K_RETURN)
            for _ in range(lamina):
                self._avanzar_una_lamina()
            tecla(self.app, pygame.K_ESCAPE)
            self.assertTrue(self._estado("seleccion"), lamina)
            self.assertTrue(self.app.intro_vista)

    def test_flujo_completo_por_teclado_menu_intro_seleccion_escena(self) -> None:
        tecla(self.app, pygame.K_RETURN)                 # menu -> intro
        for _ in range(len(self.intro.intro.laminas)):
            self._avanzar_una_lamina("tecla")            # intro -> seleccion
        self.assertTrue(self._estado("seleccion"))
        tecla(self.app, pygame.K_3)                      # rol
        tecla(self.app, pygame.K_2)                      # personaje -> escena
        self.assertTrue(self._estado("escena"))
        self.assertEqual(self.app.personaje.rol.name, "INFLUENCER")

    def test_flujo_completo_con_clics_hasta_la_escena(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        for _ in range(len(self.intro.intro.laminas)):
            self._avanzar_una_lamina("clic")
        sel = self.app.estados._actual
        clic(self.app, sel.botones[0].rect.center)       # rol
        sel = self.app.estados._actual
        clic(self.app, sel.botones[1].rect.center)       # personaje
        self.assertTrue(self._estado("escena"))

    def test_volver_desde_la_seleccion_no_repite_la_intro(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        tecla(self.app, pygame.K_ESCAPE)
        tecla(self.app, pygame.K_ESCAPE)                 # seleccion -> menu
        self.assertTrue(self._estado("menu"))
        tecla(self.app, pygame.K_RETURN)
        self.assertTrue(self._estado("seleccion"))

    # --- avance y texto --------------------------------------------------------------------
    def test_el_texto_se_escribe_letra_por_letra_con_dt(self) -> None:
        self.intro.al_entrar()
        d = self.intro.dialogo
        total = len(self.intro.lamina.texto)
        self.assertFalse(d.terminado)
        self.intro.update(1 / 60)
        primera = d._visibles
        self.assertTrue(0 < primera < 5)                  # unas pocas letras en el primer fotograma
        self.intro.update(0.5)
        self.assertGreater(d._visibles, primera)
        self.assertFalse(d.terminado)
        self.intro.update(total / CARACTERES_POR_SEGUNDO)
        self.assertTrue(d.terminado)

    def test_el_primer_clic_completa_el_texto_y_el_segundo_avanza(self) -> None:
        self.intro.al_entrar()
        self.app.estados.cambiar("intro")
        self.app.estados.update(0.1)
        self.assertFalse(self.intro.dialogo.terminado)
        clic(self.app)
        self.assertTrue(self.intro.dialogo.terminado)
        self.assertEqual((self.intro.indice, self.intro.fase in (ENTRANDO, MANTENIENDO)), (0, True))
        clic(self.app)
        self.assertEqual(self.intro.fase, SALIENDO)
        self.app.estados.update(FADE_SALIDA + 0.05)
        self.assertEqual(self.intro.indice, 1)
        self.assertFalse(self.intro.dialogo.terminado)    # la nueva lamina vuelve a escribirse

    def test_clics_repetidos_durante_el_fundido_de_salida_no_saltan_laminas(self) -> None:
        self.app.estados.cambiar("intro")
        self.intro.dialogo.completar()
        for _ in range(8):
            clic(self.app)
        self.assertEqual(self.intro.fase, SALIENDO)
        self.app.estados.update(FADE_SALIDA + 0.05)
        self.assertEqual(self.intro.indice, 1)

    def test_cualquier_tecla_avanza_pero_esc_salta(self) -> None:
        self.app.estados.cambiar("intro")
        tecla(self.app, pygame.K_a)
        self.assertTrue(self.intro.dialogo.terminado)     # una tecla cualquiera completo el texto
        tecla(self.app, pygame.K_RIGHT)
        self.assertEqual(self.intro.fase, SALIENDO)
        tecla(self.app, pygame.K_ESCAPE)
        self.assertTrue(self._estado("seleccion"))

    def test_no_avanza_sola_esperando_al_jugador(self) -> None:
        self.app.estados.cambiar("intro")
        for _ in range(60 * 30):                          # 30 s sin tocar nada
            self.app.estados.update(1 / 60)
        self.assertEqual(self.intro.indice, 0)
        self.assertEqual(self.intro.fase, MANTENIENDO)
        self.assertTrue(self.intro.dialogo.terminado)

    # --- fundidos --------------------------------------------------------------------------
    def test_fundido_de_entrada_con_dt(self) -> None:
        self.app.estados.cambiar("intro")
        self.assertEqual(self.intro.alfa, 0)
        self.app.estados.update(FADE_ENTRADA / 2)
        self.assertAlmostEqual(self.intro.alfa, 127.5, delta=1)
        self.app.estados.update(FADE_ENTRADA / 2 + 0.01)
        self.assertEqual(self.intro.alfa, 255)
        self.assertEqual(self.intro.fase, MANTENIENDO)

    def test_fundido_de_salida_con_dt(self) -> None:
        self.app.estados.cambiar("intro")
        self.app.estados.update(FADE_ENTRADA + 0.1)
        self.intro.dialogo.completar()
        clic(self.app)
        self.assertEqual(self.intro.alfa, 255)
        self.app.estados.update(FADE_SALIDA / 2)
        self.assertAlmostEqual(self.intro.alfa, 127.5, delta=1)

    def test_el_subtitulo_nunca_queda_vacio_en_todo_el_recorrido(self) -> None:
        tecla(self.app, pygame.K_RETURN)
        for _ in range(len(self.intro.intro.laminas)):
            i = self.intro.indice
            while self._estado("intro") and self.intro.indice == i:
                self.assertEqual(self.intro.dialogo.texto, self.intro.lamina.texto)
                self.assertTrue(self.intro.dialogo.texto.strip())
                clic(self.app)
                for _ in range(10):
                    self.app.estados.update(1 / 60)

    def test_dibuja_en_los_3_temas_en_todas_las_fases(self) -> None:
        for _ in range(3):
            self.app.temas.siguiente()
            self.app.estados.cambiar("intro")
            for i in range(len(self.intro.intro.laminas)):
                for f in range(80):
                    self.app.estados.update(1 / 60)
                    if f % 8 == 0:
                        self.app.estados.draw(self.app.pantalla)
                clic(self.app)
                clic(self.app)
                self.app.estados.update(FADE_SALIDA / 2)
                self.app.estados.draw(self.app.pantalla)
                self.app.estados.update(FADE_SALIDA)
                if not self._estado("intro"):
                    break


if __name__ == "__main__":
    unittest.main()
