"""Mundo caminable (models/mundo.py): datos, colisiones, deslizamiento, independencia de FPS y zona al alcance."""
import json
import math
import os
import random
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
        self.assertIsNone(m.zona_al_alcance())                # todavia no "llego" a la plaza b
        m.ultima_plaza = "b"
        self.assertEqual(m.zona_al_alcance(), "b")
        m.jugador = (600, 80 + 25)                            # justo en el radio
        self.assertEqual(m.zona_al_alcance(), "b")
        m.jugador = (600, 80 + 26)                            # justo fuera
        self.assertIsNone(m.zona_al_alcance())

    def test_cada_lugar_del_mapa_real_se_alcanza_caminando_hasta_su_entrada(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        for e in m.edificios:
            m.jugador, m.ultima_plaza = e.entrada, e.zona
            self.assertEqual(m.zona_al_alcance(), e.zona)
            self.assertEqual(m.plaza_en(e.entrada, 2 * m.radio_jugador), e.zona)   # la puerta queda "dentro"
        m.jugador, m.ultima_plaza = m.aparicion, "plaza"
        self.assertIsNone(m.zona_al_alcance())               # en el centro de la Plaza no se esta en ninguna puerta


def caminar_hacia(m: MundoCiudad, destino: tuple[float, float], llegar=None, fps: int = 60,
                  maximo: float = 30) -> bool:
    """Camina en linea recta hacia `destino` (las calles unen centros de plazas). True si llego."""
    for _ in range(round(maximo * fps)):
        dx, dy = destino[0] - m.jugador[0], destino[1] - m.jugador[1]
        if math.hypot(dx, dy) < 3:
            return True
        antes = m.jugador
        m.mover(dx, dy, 1 / fps, llegar)
        if m.jugador == antes:
            return False                                    # bloqueado
    return False


class LlegadaTest(unittest.TestCase):
    """Llegar a una plaza distinta avisa una sola vez (asi la partida queda en la misma zona)."""

    def setUp(self) -> None:
        self.llegadas: list[str] = []

    def test_cruzar_una_calle_avisa_la_llegada(self) -> None:
        m = mundo_simple()
        self.assertEqual(m.ultima_plaza, "a")
        self.assertTrue(caminar_hacia(m, (600, 100), self.llegadas.append))
        self.assertEqual(self.llegadas, ["b"])
        self.assertEqual(m.ultima_plaza, "b")

    def test_dar_la_vuelta_a_mitad_de_calle_no_avisa(self) -> None:
        m = mundo_simple()
        caminar_hacia(m, (350, 100), self.llegadas.append)   # mitad de la calle
        caminar_hacia(m, (100, 100), self.llegadas.append)   # vuelve a la plaza de origen
        self.assertEqual(self.llegadas, [])                  # nunca llego a una plaza distinta
        self.assertEqual(m.ultima_plaza, "a")

    def test_rozar_la_boca_de_otra_plaza_no_es_llegar(self) -> None:
        m = mundo_simple()
        caminar_hacia(m, (565, 100), self.llegadas.append)   # b: borde en 560; se llega a 2 radios del jugador (580)
        self.assertEqual(self.llegadas, [])                  # histeresis
        caminar_hacia(m, (590, 100), self.llegadas.append)
        self.assertEqual(self.llegadas, ["b"])

    def test_en_el_mapa_real_se_llega_por_el_camino_de_dijkstra(self) -> None:
        g = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        for origen, destino in (("barrio", "plaza"), ("colegio", "alcaldia"), ("plaza", "parque"), ("alcaldia", "barrio")):
            m = MundoCiudad.cargar(RUTA_MUNDO)
            m.jugador, m.ultima_plaza = m.plazas[origen].pos, origen
            llegadas = []
            ruta = g.ruta(origen, destino)
            for siguiente in ruta.zonas[1:]:
                self.assertTrue(caminar_hacia(m, m.plazas[siguiente].pos, llegadas.append))
            self.assertEqual(llegadas, list(ruta.zonas[1:]), (origen, destino))
            self.assertEqual(m.ultima_plaza, destino)

    def test_fuera_de_las_plazas_las_calles_del_mapa_real_no_se_solapan(self) -> None:
        m = MundoCiudad.cargar(RUTA_MUNDO)
        for c in m.calles:
            a, b = m.plazas[c.desde].pos, m.plazas[c.hasta].pos
            largo = math.dist(a, b)
            ux, uy = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
            for i in range(101):
                for desvio in range(-40, 41, 10):
                    p = (a[0] + ux * largo * i / 100 - uy * desvio, a[1] + uy * largo * i / 100 + ux * desvio)
                    if m.plaza_en(p) is not None:
                        continue
                    dentro = [o for o in m.calles if math.dist(p, _cercano(p, m, o)) <= o.ancho / 2]
                    self.assertEqual(len(dentro), 1, (c, p))

    def test_ida_y_vuelta_con_la_ultima_plaza(self) -> None:
        m = mundo_simple()
        caminar_hacia(m, (600, 100))
        copia = MundoCiudad.from_dict(json.loads(json.dumps(m.to_dict())))
        self.assertEqual((copia.ultima_plaza, copia.jugador), ("b", m.jugador))


def _cercano(p, m: MundoCiudad, calle):
    from post_truth.models.mundo import _cercano_en_segmento
    return _cercano_en_segmento(p, m.plazas[calle.desde].pos, m.plazas[calle.hasta].pos)


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

    def test_e_lejos_no_hace_nada_y_en_un_lugar_sin_nada_avisa(self) -> None:
        self.tecla(self.pygame.K_e)
        self.assertEqual(self.estado.aviso, "")
        s, m = self.app.partida, self.estado.mundo
        vacio = next(e for e in m.edificios if e.zona != s.zona_noticia
                     and e.zona not in s.jugador_actual.investigacion.lugares_pendientes())
        m.jugador, m.ultima_plaza = vacio.entrada, vacio.zona
        s.llegar(s.jugador_actual.id, vacio.zona)
        self.tecla(self.pygame.K_e)
        self.assertIn("no hay nada", self.estado.aviso)
        self.correr(5)
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



def ir_a_zona(estado, zona: str, hasta_la_puerta: bool = True) -> bool:
    """Camina como un jugador: por la ruta de Dijkstra, plaza por plaza, avisando las llegadas como el teclado."""
    m, s = estado.mundo, estado.app.partida
    for siguiente in s.mapa.ruta(m.ultima_plaza, zona).zonas[1:]:
        if not caminar_hacia(m, m.plazas[siguiente].pos, estado._llegar):
            return False
    if hasta_la_puerta:
        puerta = next(e.entrada for e in m.edificios if e.zona == zona)
        return caminar_hacia(m, puerta, estado._llegar)
    return True


class FlujoMundoNoticiasTest(unittest.TestCase):
    """Etapa M2: Seleccion -> Mundo -> (E) noticia -> decidir -> Mundo con la siguiente. La sesion manda."""

    def setUp(self) -> None:
        import pygame
        from post_truth.pygame_app import App
        self.pygame = pygame
        self.app = App()
        self.app.intro_vista = True
        self.app.estados._estados["mundo"].rng = random.Random(4)
        for k in (pygame.K_RETURN, pygame.K_2, pygame.K_1):           # menu -> seleccion -> periodista hombre
            self.tecla(k)
        self.estado = self.app.estados._actual

    def tearDown(self) -> None:
        self.pygame.quit()

    def tecla(self, key: int) -> None:
        self.app.estados.handle_event(self.pygame.event.Event(self.pygame.KEYDOWN, key=key))

    @property
    def sesion(self):
        return self.app.partida

    def sincronizados(self) -> None:
        self.assertEqual(self.sesion.jugador_actual.zona, self.estado.mundo.ultima_plaza)

    def entrar_a_la_noticia(self):
        self.assertTrue(ir_a_zona(self.estado, self.sesion.zona_noticia))
        self.assertEqual(self.estado.accion_disponible(), (self.sesion.zona_noticia, "entrar"))
        self.tecla(self.pygame.K_e)
        return self.app.estados._actual

    def decidir_y_salir(self, escena, tipo: str = "ignorar") -> None:
        from post_truth.controllers.escena_state import PROPAGACION
        nodo = next((n for n in escena.arbol.root.children if n.tipo == tipo), escena.arbol.root.children[0])
        escena._decidir(nodo)
        if escena.fase == PROPAGACION:
            escena.animacion.saltar()
            escena._terminar_propagacion()
        self.tecla(self.pygame.K_RETURN)                                 # Continuar

    def test_la_seleccion_lleva_al_mundo_con_una_partida_nueva_y_sincronizada(self) -> None:
        self.assertEqual(type(self.estado).__name__, "MundoState")
        self.assertIsNotNone(self.sesion)
        self.assertEqual(self.sesion.jugador_actual.personaje, self.app.personaje)
        self.sincronizados()

    def test_ir_a_la_noticia_y_e_abre_su_pantalla(self) -> None:
        escena = self.entrar_a_la_noticia()
        self.assertEqual(type(escena).__name__, "EscenaState")
        self.assertTrue(escena.interior)
        self.assertIs(escena.sesion, self.sesion)                        # la misma partida, no una nueva
        self.assertEqual(escena.zona, self.sesion.zona_noticia)
        self.sincronizados()

    def test_al_decidir_se_vuelve_a_la_calle_con_la_siguiente_noticia(self) -> None:
        primera = self.sesion.arbol
        escena = self.entrar_a_la_noticia()
        self.decidir_y_salir(escena)
        self.assertIs(self.app.estados._actual, self.estado)
        self.assertEqual(self.sesion.indice, 1)
        self.assertIsNot(self.sesion.arbol, primera)
        self.assertEqual(self.estado.estado_vista().noticia, self.sesion.zona_noticia)   # la marca se movio
        self.sincronizados()

    def test_esc_en_el_interior_vuelve_a_la_calle_sin_decidir(self) -> None:
        self.entrar_a_la_noticia()
        self.tecla(self.pygame.K_ESCAPE)
        self.assertIs(self.app.estados._actual, self.estado)
        self.assertEqual(self.sesion.indice, 0)                         # la noticia sigue pendiente
        self.assertIsNotNone(self.app.partida)

    def test_buscar_evidencia_en_otro_lugar_la_revela(self) -> None:
        s = self.sesion
        while not (s.jugador_actual.investigacion.lugares_pendientes() - {s.zona_noticia}):
            s.abrir_evento(s.indice + 1)                                 # una noticia con evidencia en otro lugar
        inv = s.jugador_actual.investigacion
        lugar = min(inv.lugares_pendientes() - {s.zona_noticia})
        self.assertTrue(ir_a_zona(self.estado, lugar))
        self.assertEqual(self.estado.accion_disponible(), (lugar, "evidencia"))
        self.tecla(self.pygame.K_e)
        evidencia = inv.evidencia_en(lugar)
        self.assertTrue(inv.esta_descubierta(evidencia.id))
        self.assertIn(evidencia.titulo, self.estado.aviso)
        self.assertIsNone(self.estado.accion_disponible())               # ya no hay nada que buscar aqui
        self.sincronizados()

    def test_g_muestra_la_guia_hacia_la_noticia(self) -> None:
        self.assertEqual(self.estado.estado_vista().guia, ())
        self.tecla(self.pygame.K_g)
        vista = self.estado.estado_vista()
        self.assertEqual(vista.guia[0], self.estado.mundo.ultima_plaza)
        self.assertEqual(vista.guia[-1], self.sesion.zona_noticia)
        self.assertEqual(list(vista.guia),
                         list(self.sesion.mapa.ruta(vista.guia[0], vista.guia[-1]).zonas))   # es el camino de Dijkstra
        self.tecla(self.pygame.K_g)
        self.assertEqual(self.estado.estado_vista().guia, ())

    def test_hud_marcas_guia_y_minimapa_se_dibujan_en_los_3_temas(self) -> None:
        imagenes = set()
        self.tecla(self.pygame.K_g)
        for _ in range(3):
            self.app.estados.draw(self.app.pantalla)
            imagenes.add(self.pygame.image.tobytes(self.app.pantalla, "RGB"))
            self.app.temas.siguiente()
        self.assertEqual(len(imagenes), 3)

    def test_una_partida_completa_caminando(self) -> None:
        """Bot que camina: noticia por noticia busca toda la evidencia de otros lugares, entra y decide."""
        from post_truth.controllers.escena_state import FIN
        s = self.sesion
        tipos = ("verificar", "compartir", "reportar", "ignorar")
        for i in range(len(s.arboles)):
            self.assertIs(self.app.estados._actual, self.estado)
            inv = s.jugador_actual.investigacion
            for lugar in sorted(inv.lugares_pendientes() - {s.zona_noticia}):
                self.assertTrue(ir_a_zona(self.estado, lugar))
                self.tecla(self.pygame.K_e)
                self.sincronizados()
            self.assertEqual(inv.lugares_pendientes() - {s.zona_noticia}, set())
            escena = self.entrar_a_la_noticia()
            self.app.estados.draw(self.app.pantalla)
            self.decidir_y_salir(escena, tipos[i % 4])
        escena = self.app.estados._actual
        self.assertEqual(escena.fase, FIN)
        self.tecla(self.pygame.K_RETURN)                                 # Volver al menu
        self.assertEqual(type(self.app.estados._actual).__name__, "MenuState")
        self.assertIsNone(self.app.partida)

    def test_el_respaldo_lleva_a_la_escena_como_antes(self) -> None:
        self.tecla(self.pygame.K_ESCAPE)                                 # abandona la partida del mundo
        self.assertIsNone(self.app.partida)
        self.app.flujo = "escena"
        for k in (self.pygame.K_RETURN, self.pygame.K_1, self.pygame.K_2):
            self.tecla(k)
        escena = self.app.estados._actual
        self.assertEqual(type(escena).__name__, "EscenaState")
        self.assertFalse(escena.interior)


if __name__ == "__main__":
    unittest.main()
