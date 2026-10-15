"""Mundo caminable (models/mundo.py): datos, colisiones, deslizamiento, independencia de FPS y zona al alcance."""
import json
import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_GRAFO_CIUDAD, RUTA_MUNDO
from post_truth.models.mundo import MundoCiudad
from post_truth.structures.grafo_ciudad import GrafoCiudad


def datos() -> dict:
    return json.loads(Path(RUTA_MUNDO).read_text(encoding="utf-8"))


def mundo_simple(**cambios) -> MundoCiudad:
    """Dos plazas unidas por una calle horizontal y otra que baja en diagonal (a 45 grados)."""
    d = {"tamano": [1000, 1000], "radio_jugador": 10, "velocidad": 100,
         "zonas": {"a": {"pos": [100, 100], "radio": 40}, "b": {"pos": [600, 100], "radio": 40},
                   "c": {"pos": [900, 400], "radio": 40}},
         "calles": [{"desde": "a", "hasta": "b", "ancho": 60}, {"desde": "b", "hasta": "c", "ancho": 60}],
         "edificios": [{"zona": "b", "rect": [560, 0, 80, 40], "entrada": [600, 80], "radio": 25}],
         "aparicion": [100, 100]}
    d.update(cambios)
    return MundoCiudad.from_dict(d)


class DatosTest(unittest.TestCase):
    def test_mundo_json_carga_y_sigue_al_grafo_de_la_ciudad(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        g = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        self.assertEqual(set(m.plazas), {z.id for z in g.zonas()})
        calles = {frozenset((c.desde, c.hasta)) for c in m.calles}
        self.assertEqual(calles, {frozenset((a, b)) for a, b, _ in g.conexiones()})   # una calle por arista
        ancho, alto = m.tamano
        for z in g.zonas():                                                              # misma disposicion
            x, y = m.plazas[z.id].pos
            self.assertTrue(0 < x < ancho and 0 < y < alto)
            for otra in g.zonas():
                ox, oy = m.plazas[otra.id].pos
                self.assertEqual((x < ox, y < oy), (z.pos[0] < otra.pos[0], z.pos[1] < otra.pos[1]))
        self.assertEqual({e.zona for e in m.edificios}, set(m.plazas))                   # un edificio por zona
        self.assertEqual(m.jugador, m.aparicion)
        self.assertEqual(m.plazas[g.zona_inicial].pos, m.aparicion)

    def test_datos_invalidos_se_rechazan(self) -> None:
        malos = [
            {"calles": [{"desde": "a", "hasta": "x", "ancho": 60}]},                    # plaza desconocida
            {"calles": [{"desde": "a", "hasta": "b", "ancho": 15}]},                    # mas angosta que el jugador
            {"aparicion": [500, 500]},                                                    # fuera de las calles
            {"edificios": [{"zona": "b", "rect": [0, 0, 1, 1], "entrada": [600, 300], "radio": 20}]},
            {"edificios": [{"zona": "x", "rect": [0, 0, 1, 1], "entrada": [100, 100], "radio": 20}]},
            {"velocidad": 0},
            {"jugador": [500, 500]},
        ]
        for cambio in malos:
            with self.assertRaises(ValueError, msg=cambio):
                mundo_simple(**cambio)

    def test_ida_y_vuelta(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        m.mover(1, 0, 0.7)
        copia = MundoCiudad.from_dict(json.loads(json.dumps(m.to_dict())))
        self.assertEqual(copia.to_dict(), m.to_dict())
        self.assertEqual(copia.jugador, m.jugador)


class ColisionTest(unittest.TestCase):
    def test_solo_se_esta_sobre_calles_y_plazas(self) -> None:
        m = mundo_simple()
        self.assertTrue(m.es_transitable((100, 100)))        # centro de una plaza
        self.assertTrue(m.es_transitable((350, 100)))        # mitad de la calle
        self.assertTrue(m.es_transitable((350, 119)))        # borde de la calle menos el radio del jugador
        self.assertFalse(m.es_transitable((350, 121)))       # el cuerpo del jugador ya se saldria
        self.assertFalse(m.es_transitable((350, 300)))       # campo abierto

    def test_nunca_sale_de_lo_transitable_en_ninguna_direccion(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        for i in range(64):
            angulo = i * math.tau / 64
            m.mover(math.cos(angulo), math.sin(angulo), 0.9)
            self.assertTrue(m.es_transitable(m.jugador), f"angulo {i}: {m.jugador}")

    def test_contra_una_pared_no_avanza(self) -> None:
        m = mundo_simple()
        m.mover(0, 1, 2.0)                                    # hacia abajo desde el centro de la plaza a
        self.assertAlmostEqual(m.jugador[1], 100 + 30, places=6)   # se queda en el borde (radio 40 - 10)
        self.assertAlmostEqual(m.jugador[0], 100, places=6)

    def test_sin_direccion_o_sin_tiempo_no_se_mueve(self) -> None:
        m = mundo_simple()
        m.mover(0, 0, 1)
        m.mover(1, 0, 0)
        self.assertEqual(m.jugador, (100.0, 100.0))

    def test_la_diagonal_no_es_mas_rapida(self) -> None:
        m = mundo_simple(zonas={"a": {"pos": [500, 500], "radio": 400}}, calles=[], edificios=[],
                         aparicion=[500, 500], tamano=[1000, 1000])
        m.mover(1, 1, 1.0)
        self.assertAlmostEqual(math.dist(m.jugador, (500, 500)), 100, places=6)


class DeslizamientoTest(unittest.TestCase):
    def test_empujar_en_diagonal_contra_el_borde_de_una_calle_recta_avanza_a_lo_largo(self) -> None:
        m = mundo_simple(jugador=[300, 100])
        m.mover(1, 1, 1.0)                                    # 100 px/s en diagonal: 70.7 hacia la derecha
        x, y = m.jugador
        self.assertAlmostEqual(y, 120, places=6)              # pegado al borde de abajo (30 - 10)
        self.assertGreater(x, 300 + 60)                       # pero avanzo casi todo lo que pedia en x
        self.assertTrue(m.es_transitable(m.jugador))

    def test_en_una_calle_diagonal_tambien_resbala(self) -> None:
        m = mundo_simple(jugador=[750, 250])                  # mitad de la calle b-c (a 45 grados)
        m.mover(1, 0, 1.0)                                    # empuja a la derecha; la calle baja hacia c
        x, y = m.jugador
        self.assertTrue(m.es_transitable(m.jugador))
        self.assertGreater(x, 750 + 20)                       # avanzo hacia c
        self.assertGreater(y, 250)                            # siguiendo la calle (que baja hacia c)

    def test_sigue_una_calle_de_punta_a_punta(self) -> None:
        m = mundo_simple()
        m.mover(1, 0, 5.0)                                    # 500 px: de la plaza a hasta la plaza b
        self.assertAlmostEqual(m.jugador[0], 600, places=6)


class IndependenciaDeFpsTest(unittest.TestCase):
    RECORRIDO = [((1, 0), 0.8), ((1, -1), 0.5), ((0, 1), 0.6), ((-1, 0.3), 0.7), ((1, 1), 0.4)]  # 3 s con choques

    def _jugar(self, fps: int) -> tuple[float, float]:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        for (dx, dy), segundos in self.RECORRIDO:
            for _ in range(round(segundos * fps)):
                m.mover(dx, dy, 1 / fps)
        return m.jugador

    def test_el_mismo_recorrido_termina_igual_a_30_y_a_60_fps(self) -> None:
        a, b = self._jugar(30), self._jugar(60)
        self.assertLess(math.dist(a, b), 1e-6, (a, b))
        self.assertNotEqual(a, MundoCiudad.cargar(RUTA_MUNDO).aparicion)   # de verdad se movio

    def test_un_dt_grande_no_atraviesa_paredes(self) -> None:
        m = mundo_simple()
        m.mover(0, 1, 10.0)                                   # 1000 px de golpe hacia campo abierto
        self.assertTrue(m.es_transitable(m.jugador))


class ZonaAlAlcanceTest(unittest.TestCase):
    def test_en_la_entrada_la_zona_y_lejos_ninguna(self) -> None:
        m = mundo_simple()
        self.assertIsNone(m.zona_al_alcance())                # en la plaza a: su edificio no existe
        m.jugador = (600, 80)
        self.assertEqual(m.zona_al_alcance(), "b")
        m.jugador = (600, 80 + 25)                            # justo en el radio
        self.assertEqual(m.zona_al_alcance(), "b")
        m.jugador = (600, 80 + 26)                            # justo fuera
        self.assertIsNone(m.zona_al_alcance())

    def test_cada_lugar_del_mapa_real_se_alcanza_caminando_hasta_su_entrada(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        for e in m.edificios:
            m.jugador = e.entrada
            self.assertEqual(m.zona_al_alcance(), e.zona)
        m.jugador = m.aparicion
        self.assertIsNone(m.zona_al_alcance())               # en el centro de la Plaza no se esta en ninguna puerta


class MundoEnPantallaTest(unittest.TestCase):
    """MundoState con eventos de teclado (sin ventana), camara y dibujo en los 3 temas."""

    def setUp(self) -> None:
        import pygame
        from post_truth.pygame_app import App
        self.pygame = pygame
        self.app = App()
        self.app.intro_vista = True
        self.tecla(pygame.K_m)                                         # desde el menu
        self.estado = self.app.estados._actual

    def tearDown(self) -> None:
        self.pygame.quit()

    def tecla(self, key: int, tipo=None) -> None:
        self.app.estados.handle_event(self.pygame.event.Event(tipo or self.pygame.KEYDOWN, key=key))

    def correr(self, segundos: float, fps: int = 60) -> None:
        for _ in range(round(segundos * fps)):
            self.app.estados.update(1 / fps)

    def test_el_menu_abre_el_mundo_en_el_punto_de_aparicion(self) -> None:
        self.assertEqual(type(self.estado).__name__, "MundoState")
        self.assertEqual(self.estado.mundo.jugador, self.estado.mundo.aparicion)

    def test_wasd_y_flechas_mueven_y_soltar_detiene(self) -> None:
        pg = self.pygame
        for teclas, eje, signo in (((pg.K_d, pg.K_RIGHT), 0, 1), ((pg.K_a, pg.K_LEFT), 0, -1),
                                   ((pg.K_s, pg.K_DOWN), 1, 1), ((pg.K_w, pg.K_UP), 1, -1)):
            for t in teclas:
                self.estado.mundo.jugador = self.estado.mundo.aparicion
                antes = self.estado.mundo.jugador
                self.tecla(t)
                self.correr(0.2)
                self.tecla(t, pg.KEYUP)
                movido = self.estado.mundo.jugador
                self.assertGreater((movido[eje] - antes[eje]) * signo, 30, pg.key.name(t))
                self.correr(0.2)
                self.assertEqual(self.estado.mundo.jugador, movido)      # soltar la tecla lo detiene

    def test_teclas_opuestas_se_anulan(self) -> None:
        self.tecla(self.pygame.K_a)
        self.tecla(self.pygame.K_d)
        self.correr(0.5)
        self.assertEqual(self.estado.mundo.jugador, self.estado.mundo.aparicion)

    def test_e_en_una_entrada_avisa_y_lejos_no(self) -> None:
        self.tecla(self.pygame.K_e)
        self.assertEqual(self.estado.aviso, "")
        self.estado.mundo.jugador = self.estado.mundo.edificios[0].entrada
        self.tecla(self.pygame.K_e)
        self.assertIn(self.estado.mundo.edificios[0].zona.capitalize(), self.estado.aviso)
        self.correr(3)
        self.assertEqual(self.estado.aviso, "")                          # el aviso se va solo

    def test_esc_vuelve_al_menu_y_la_siguiente_visita_empieza_de_nuevo(self) -> None:
        self.tecla(self.pygame.K_d)
        self.correr(0.3)
        self.tecla(self.pygame.K_ESCAPE)
        self.assertEqual(type(self.app.estados._actual).__name__, "MenuState")
        self.tecla(self.pygame.K_m)
        self.assertEqual(self.estado.mundo.jugador, self.estado.mundo.aparicion)
        self.correr(0.3)
        self.assertEqual(self.estado.mundo.jugador, self.estado.mundo.aparicion)   # no quedo una tecla pegada

    def test_la_camara_sigue_al_jugador_sin_salirse_del_mundo(self) -> None:
        from post_truth.config import ALTO, ANCHO, ESCALA
        from post_truth.views.mundo_view import camara
        m = self.estado.mundo
        vista = (ANCHO / ESCALA, ALTO / ESCALA)
        x, y = camara(m)
        self.assertAlmostEqual(x + vista[0] / 2, m.jugador[0])           # en el centro: centrada en el jugador
        self.assertAlmostEqual(y + vista[1] / 2, m.jugador[1])
        for e in m.edificios:                                            # en las esquinas: no se sale
            m.jugador = e.entrada
            x, y = camara(m)
            self.assertTrue(0 <= x <= m.tamano[0] - vista[0] and 0 <= y <= m.tamano[1] - vista[1], e.zona)

    def test_se_dibuja_en_los_3_temas_cerca_de_cada_lugar(self) -> None:
        imagenes = set()
        for _ in range(3):
            for e in self.estado.mundo.edificios:
                self.estado.mundo.jugador = e.entrada
                self.app.estados.draw(self.app.pantalla)
                imagenes.add(self.pygame.image.tobytes(self.app.pantalla, "RGB"))
            self.app.temas.siguiente()
        self.assertEqual(len(imagenes), 15)                              # 5 lugares x 3 temas, todos distintos

    def test_el_arte_se_puede_reemplazar_sin_tocar_el_modelo(self) -> None:
        from post_truth.views.arte_mundo import ArteFormas
        from post_truth.views.mundo_view import dibujar_mundo
        llamadas = []

        class ArteEspia(ArteFormas):
            def __getattribute__(self, nombre):
                if not nombre.startswith("_"):
                    llamadas.append(nombre)
                return super().__getattribute__(nombre)
        m = self.estado.mundo
        dibujar_mundo(self.app.pantalla, self.app.fuentes, self.app.temas.actual, m, arte=ArteEspia())
        self.assertEqual(set(llamadas), {"suelo", "calle", "plaza", "edificio", "personaje"})
        self.assertEqual(llamadas.count("calle"), len(m.calles))


if __name__ == "__main__":
    unittest.main()
