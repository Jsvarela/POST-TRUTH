"""Escala de la interfaz: la geometria crece de forma uniforme y todo cabe en la ventana."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pygame

from post_truth import config
from post_truth.config import ALTO, ANCHO, DISENO_ALTO, DISENO_ANCHO, ESCALA, px
from post_truth.controllers.escena_state import RECT_BOTON_CENTRAL, RECT_DIALOGO, Y_BOTONES, ALTO_BOTONES, _rects_botones
from post_truth.controllers.intro_state import RECT_SUBTITULO
from post_truth.escala import ESCALA_MAXIMA, ESCALA_MINIMA, escala_para_pantalla
from post_truth.views.componentes import Fuentes
from post_truth.views.escena_view import RECT_ESCENA, RECT_HUD, RECT_MAPA, RECT_PANEL, RECT_PERSONAJE, RECT_TARJETA
from post_truth.views.iconos import fila_de_rayos, rayo
from post_truth.views.intro_view import ALTO_ARTE
from post_truth.views.theme import TEMAS


class EscalaTest(unittest.TestCase):
    def test_por_defecto_la_ventana_es_un_cuarto_mas_grande_que_el_diseno(self) -> None:
        self.assertEqual(ESCALA, 1.25)
        self.assertEqual((ANCHO, ALTO), (1280, 800))
        self.assertEqual((px(DISENO_ANCHO), px(DISENO_ALTO)), (ANCHO, ALTO))

    def test_px_escala_y_redondea(self) -> None:
        self.assertEqual(px(0), 0)
        self.assertEqual(px(100), 125)
        self.assertEqual(px(8), 10)
        self.assertIsInstance(px(7.5), int)

    def test_las_fuentes_crecen_con_la_escala_y_son_legibles(self) -> None:
        pygame.init()
        f = Fuentes.crear()
        # El texto mas pequeno (chica) ya no es de 16 px: a escala 1.25 mide al menos 21 px de alto de linea
        self.assertGreaterEqual(f.chica.get_height(), 20)
        self.assertTrue(f.chica.get_height() < f.normal.get_height() < f.grande.get_height() < f.titulo.get_height())
        pygame.quit()


class EscalaSegunLaPantallaTest(unittest.TestCase):
    def test_pantallas_grandes_usan_la_escala_maxima(self) -> None:
        for alto in (1080, 1200, 1440, 2160):
            self.assertEqual(escala_para_pantalla(alto), ESCALA_MAXIMA, alto)

    def test_pantallas_bajas_reducen_la_escala_para_que_la_ventana_quepa(self) -> None:
        for alto in (720, 768, 800, 864, 900):
            e = escala_para_pantalla(alto)
            self.assertGreaterEqual(e, ESCALA_MINIMA)
            self.assertLessEqual(e, ESCALA_MAXIMA)
            if e > ESCALA_MINIMA:
                self.assertLessEqual(round(DISENO_ALTO * e), alto - 90, alto)   # cabe con barra de titulo y de tareas
        self.assertEqual(escala_para_pantalla(720), ESCALA_MINIMA)
        self.assertLess(escala_para_pantalla(864), ESCALA_MAXIMA)

    def test_nunca_baja_del_tamano_original_ni_pasa_del_maximo(self) -> None:
        for alto in range(300, 3000, 37):
            self.assertTrue(ESCALA_MINIMA <= escala_para_pantalla(alto) <= ESCALA_MAXIMA)

    def test_alto_desconocido_usa_la_escala_maxima(self) -> None:
        self.assertEqual(escala_para_pantalla(0), ESCALA_MAXIMA)
        self.assertEqual(escala_para_pantalla(-1), ESCALA_MAXIMA)

    def test_la_escala_crece_con_el_alto_de_la_pantalla(self) -> None:
        escalas = [escala_para_pantalla(a) for a in range(700, 1000, 10)]
        self.assertEqual(escalas, sorted(escalas))

    def test_leer_la_pantalla_no_rompe_el_video_ya_iniciado_ni_sus_temporizadores(self) -> None:
        """Regresion: elegir la escala no debe cerrar el video de pygame si alguien ya lo esta usando
        (se perdia la cola de eventos y un QUIT diferido nunca llegaba, dejando el juego colgado)."""
        from post_truth.escala import _alto_del_escritorio
        pygame.init()
        pygame.display.set_mode((200, 100))
        pygame.time.set_timer(pygame.QUIT, 150, loops=1)
        _alto_del_escritorio()
        self.assertTrue(pygame.display.get_init())
        for _ in range(60):                                   # hasta ~0.6 s esperando el QUIT diferido
            if any(e.type == pygame.QUIT for e in pygame.event.get()):
                break
            pygame.time.wait(10)
        else:
            self.fail("el QUIT diferido se perdio")
        pygame.quit()

    def test_el_entorno_manda(self) -> None:
        resultado = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, 'src');"
             "from post_truth.escala import fijar_escala_inicial; print(fijar_escala_inicial())"],
            cwd=RAIZ, env={**os.environ, "POSTTRUTH_ESCALA": "1.1"}, capture_output=True, text=True)
        self.assertEqual(resultado.stdout.strip().splitlines()[-1], "1.1")


class GeometriaCabeEnLaVentanaTest(unittest.TestCase):
    """Todo lo que se dibuja con coordenadas fijas debe caber en la ventana y no solaparse."""
    VENTANA = pygame.Rect(0, 0, ANCHO, ALTO)

    def test_las_zonas_principales_de_la_escena_caben(self) -> None:
        for nombre, rect in (("hud", RECT_HUD), ("personaje", RECT_PERSONAJE), ("panel", RECT_PANEL),
                             ("escena", RECT_ESCENA), ("dialogo", RECT_DIALOGO), ("central", RECT_BOTON_CENTRAL)):
            self.assertTrue(self.VENTANA.contains(rect), nombre)

    def test_la_tarjeta_y_el_mapa_caben_en_el_panel_y_no_se_tocan(self) -> None:
        self.assertTrue(RECT_PANEL.contains(RECT_TARJETA))
        self.assertTrue(RECT_PANEL.contains(RECT_MAPA))
        self.assertFalse(RECT_TARJETA.colliderect(RECT_MAPA))

    def test_el_orden_vertical_de_la_escena(self) -> None:
        self.assertLessEqual(RECT_HUD.bottom, RECT_ESCENA.top + px(1))
        self.assertLessEqual(RECT_ESCENA.bottom, RECT_DIALOGO.top)
        self.assertLessEqual(RECT_PANEL.bottom, RECT_DIALOGO.top)
        self.assertLessEqual(RECT_PERSONAJE.bottom, RECT_DIALOGO.top)
        self.assertLessEqual(RECT_DIALOGO.bottom, Y_BOTONES)
        self.assertLess(Y_BOTONES + ALTO_BOTONES, ALTO)

    def test_los_botones_de_decision_caben_y_no_se_pisan(self) -> None:
        for n in (3, 4):
            rects = _rects_botones(n)
            for i, r in enumerate(rects):
                self.assertTrue(self.VENTANA.contains(r))
                for r2 in rects[i + 1:]:
                    self.assertFalse(r.colliderect(r2))

    def test_la_introduccion_deja_sitio_al_subtitulo(self) -> None:
        self.assertLess(ALTO_ARTE, RECT_SUBTITULO.top)
        self.assertTrue(self.VENTANA.contains(RECT_SUBTITULO))
        self.assertLess(RECT_SUBTITULO.bottom + px(20), ALTO)         # y queda sitio para la ayuda

    def test_los_personajes_no_tapan_las_etiquetas_de_la_esquina(self) -> None:
        """"Estas en" y "Energia" viven arriba a la izquierda: la cabeza del personaje queda debajo de ellas."""
        from post_truth.views.personaje_view import ALTO_U, ANCHO_U
        pygame.init()
        f = Fuentes.crear()
        borde_inferior_de_la_energia = RECT_ESCENA.y + px(56) + f.normal.get_height() + px(10)
        s = min(RECT_PERSONAJE.width / ANCHO_U, RECT_PERSONAJE.height / ALTO_U)
        coronilla = RECT_PERSONAJE.bottom - ALTO_U * s + 24 * s     # el pelo empieza en y = 24 de la caja de diseno
        self.assertGreaterEqual(coronilla, borde_inferior_de_la_energia)
        pygame.quit()


SCRIPT_ESCALA = """
import os, random, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, "src")
import pygame
from post_truth.config import ANCHO, ALTO, ESCALA, px
from post_truth.pygame_app import App
from post_truth.views.escena_view import RECT_MAPA, RECT_TARJETA
from post_truth.views.mapa_view import _posiciones

a = App()
assert a.pantalla.get_size() == (ANCHO, ALTO) == (px(1024), px(640)), (a.pantalla.get_size(), ESCALA)
def k(key): a.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
def dibujar(n=1):
    for _ in range(n):
        a.estados.update(0.3); a.estados.draw(a.pantalla)
dibujar()
k(pygame.K_RETURN)                                   # menu -> intro
for _ in range(6):                                   # todas las laminas
    dibujar(4); a.estados._actual.dialogo.completar(); dibujar(); k(pygame.K_SPACE); a.estados.update(0.8)
assert type(a.estados._actual).__name__ == "SeleccionState", type(a.estados._actual).__name__
dibujar(); k(pygame.K_3); dibujar(); k(pygame.K_2)  # seleccion de rol y de personaje
e = a.estados._estados["escena"]; e.rng = random.Random(3)
dibujar(2)
pos = _posiciones(e._estado_mapa(), RECT_MAPA)["colegio"]
a.estados.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
dibujar()                                            # mapa con la franja de ayuda
k(pygame.K_a); k(pygame.K_q); dibujar()              # investigar y viajar
k(pygame.K_1)                                        # compartir: animacion del grafo social
for _ in range(60 * 20):
    a.estados.update(1 / 60)
    if e.botones[0].texto.startswith("Ver"): break
dibujar(); k(pygame.K_RETURN); dibujar(2)            # consecuencias
print("OK", ANCHO, ALTO)
"""


class JuegoCompletoEnVariasEscalasTest(unittest.TestCase):
    """Corre el flujo Menu -> Intro -> Seleccion -> Escena (investigar, viajar, propagacion) en otras escalas."""

    def _correr(self, escala: str) -> str:
        r = subprocess.run([sys.executable, "-c", SCRIPT_ESCALA], cwd=RAIZ,
                           env={**os.environ, "POSTTRUTH_ESCALA": escala}, capture_output=True, text=True, timeout=240)
        self.assertEqual(r.returncode, 0, f"escala {escala}: {r.stderr[-800:]}")
        return r.stdout.strip().splitlines()[-1]

    def test_escala_original_1_0(self) -> None:
        self.assertEqual(self._correr("1.0"), "OK 1024 640")

    def test_escala_intermedia_1_1(self) -> None:
        self.assertEqual(self._correr("1.1"), "OK 1126 704")

    def test_escala_por_defecto_1_25(self) -> None:
        self.assertEqual(self._correr("1.25"), "OK 1280 800")

    def test_escala_grande_1_5(self) -> None:
        self.assertEqual(self._correr("1.5"), "OK 1536 960")


class IconosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.s = pygame.display.set_mode((200, 100))

    def _img(self, **kw) -> bytes:
        self.s.fill((0, 0, 0))
        rayo(self.s, (255, 255, 0), (50, 50), 20, **kw)
        return pygame.image.tobytes(self.s, "RGB")

    def test_el_rayo_lleno_y_el_vacio_son_distintos_y_no_estan_en_blanco(self) -> None:
        lleno, vacio = self._img(lleno=True), self._img(lleno=False)
        en_blanco = bytes(200 * 100 * 3)
        self.assertNotEqual(lleno, vacio)
        self.assertNotEqual(lleno, en_blanco)
        self.assertNotEqual(vacio, en_blanco)

    def test_fila_de_rayos_rellena_los_primeros(self) -> None:
        self.s.fill((0, 0, 0))
        fila_de_rayos(self.s, (255, 255, 0), 20, 50, 5, 12, 30, llenos=2)
        a = pygame.image.tobytes(self.s, "RGB")
        self.s.fill((0, 0, 0))
        fila_de_rayos(self.s, (255, 255, 0), 20, 50, 5, 12, 30, llenos=4)
        self.assertNotEqual(a, pygame.image.tobytes(self.s, "RGB"))

    def test_fila_devuelve_donde_termina(self) -> None:
        self.assertEqual(fila_de_rayos(self.s, (1, 1, 1), 10, 50, 3, 8, 20), 10 + 2 * 20 + 8)


class EnergiaConRayosTest(unittest.TestCase):
    """La energia se ve siempre como rayos (HUD, costo de una pista de la tarjeta y viajes del mapa)."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        cls.fuentes = Fuentes.crear()

    def _etiqueta(self, energia: int) -> bytes:
        from post_truth.models.pistas import Investigacion
        from post_truth.views.escena_view import _dibujar_energia
        inv = Investigacion((), energia_max=5, energia=energia)
        self.pantalla.fill((0, 0, 0))
        _dibujar_energia(self.pantalla, self.fuentes, TEMAS["normal"], inv, px(60))
        return pygame.image.tobytes(self.pantalla.subsurface(pygame.Rect(0, px(50), px(330), px(70))), "RGB")

    def test_la_etiqueta_de_energia_muestra_un_rayo_por_unidad(self) -> None:
        imagenes = {self._etiqueta(n) for n in range(6)}
        self.assertEqual(len(imagenes), 6)                      # 0, 1, 2, 3, 4 y 5 rayos llenos se ven distintos

    def test_el_costo_de_una_pista_se_dibuja_con_rayos(self) -> None:
        from post_truth.models.pistas import Pista, Senal, ZonaTarjeta
        from post_truth.views.tarjeta_civitas_view import _insignia

        def costo(c: int) -> bytes:
            self.pantalla.fill((0, 0, 0))
            p = Pista("x", ZonaTarjeta.AUTOR, "t", "h", Senal.FALSA, c)
            _insignia(self.pantalla, self.fuentes, TEMAS["normal"], (px(300), px(100)), p, False, "A")
            return pygame.image.tobytes(self.pantalla.subsurface(pygame.Rect(px(200), px(60), px(160), px(80))), "RGB")

        self.assertEqual(len({costo(1), costo(2), costo(3)}), 3)

    def test_el_titulo_de_consecuencias_cabe_junto_al_mapa(self) -> None:
        from post_truth.views.escena_view import RECT_MAPA, RECT_PANEL
        ancho_titulo = self.fuentes.grande.size("Consecuencias")[0]
        self.assertLess(RECT_PANEL.x + px(18) + ancho_titulo, RECT_MAPA.left)


if __name__ == "__main__":
    unittest.main()
