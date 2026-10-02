import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import ALTO, ANCHO, RUTA_GRAFO_CIUDAD, px
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.escena_view import RECT_MAPA as RECT_MAPA_ESCENA
from post_truth.views.mapa_view import EstadoMapa, RADIO, _posiciones, dibujar_mapa, zona_en
from post_truth.views.theme import TEMAS
from post_truth.views.zona_view import dibujar_fondo_zona

RECT_MAPA = pygame.Rect(0, 0, RECT_MAPA_ESCENA.width, RECT_MAPA_ESCENA.height)   # el minimapa de la escena


class ZonasViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        cls.fuentes = Fuentes.crear()
        cls.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    def test_cada_zona_tiene_un_fondo_distinto(self) -> None:
        tema = TEMAS["normal"]
        rect = pygame.Rect(0, 57, 1024, 347)
        imagenes = []
        for z in self.ciudad.zonas():
            self.pantalla.fill((0, 0, 0))
            dibujar_fondo_zona(self.pantalla, z.id, tema, rect)
            imagenes.append(pygame.image.tobytes(self.pantalla.subsurface(rect), "RGB"))
        self.assertEqual(len(set(imagenes)), len(imagenes))   # no hay dos fondos iguales

    def test_fondos_en_todos_los_temas_y_zona_desconocida(self) -> None:
        rect = pygame.Rect(0, 57, 1024, 347)
        for tema in TEMAS.values():
            for z in [z.id for z in self.ciudad.zonas()] + ["zona-inventada"]:
                dibujar_fondo_zona(self.pantalla, z, tema, rect)

    def test_el_fondo_usa_solo_colores_del_tema(self) -> None:
        """Con colores distintos por tema, el mismo fondo cambia: nada esta fijo en la vista."""
        rect = pygame.Rect(0, 57, 1024, 347)
        dibujos = []
        for tema in TEMAS.values():
            self.pantalla.fill((0, 0, 0))
            dibujar_fondo_zona(self.pantalla, "plaza", tema, rect)
            dibujos.append(pygame.image.tobytes(self.pantalla.subsurface(rect), "RGB"))
        self.assertEqual(len(set(dibujos)), 3)

    def test_zona_en_acierta_en_el_centro_de_cada_nodo_y_falla_fuera(self) -> None:
        estado = EstadoMapa(self.ciudad, "plaza")
        for id, punto in _posiciones(estado, RECT_MAPA).items():
            self.assertEqual(zona_en(estado, RECT_MAPA, punto), id)
        self.assertIsNone(zona_en(estado, RECT_MAPA, (RECT_MAPA.right - 1, RECT_MAPA.centery)))

    # --- minimapa nuevo: lugares de investigacion con distancias --------------------------------
    def _estado(self, actual: str = "plaza", **kw) -> EstadoMapa:
        base = {"costos": self.ciudad.costos_desde(actual), "energia": 5}
        base.update(kw)
        return EstadoMapa(self.ciudad, actual, **base)

    def _imagen(self, estado: EstadoMapa, tema_id: str = "normal") -> bytes:
        tema = TEMAS[tema_id]
        self.pantalla.fill((0, 0, 0))
        dibujar_mapa(self.pantalla, self.fuentes, tema, RECT_MAPA, estado)
        return pygame.image.tobytes(self.pantalla.subsurface(RECT_MAPA), "RGB")

    def test_mapa_dibuja_todos_los_estados_en_todos_los_temas(self) -> None:
        ruta = self.ciudad.ruta("plaza", "barrio")
        estados = [
            self._estado(),
            self._estado(pendientes={"colegio", "alcaldia"}, revisadas={"barrio"}, teclas=True),
            self._estado(ruta=ruta.zonas, costo_ruta=ruta.costo, hover="barrio", teclas=True),
            self._estado(energia=0, hover="alcaldia"),      # todo apagado: no alcanza para ningun viaje
            self._estado("colegio", ruta=("colegio", "plaza"), costo_ruta=2, pendientes={"colegio"}, hover="colegio"),
            self._estado(hover="parque", revisadas={"parque"}),
            EstadoMapa(self.ciudad, "colegio"),             # el minimo
            EstadoMapa(self.ciudad, "colegio", mostrar_ayuda=False),   # como lo usa la introduccion
        ]
        for tema in TEMAS:
            for estado in estados:
                self._imagen(estado, tema)

    def test_la_zona_actual_se_distingue_de_las_demas(self) -> None:
        self.assertNotEqual(self._imagen(self._estado("plaza")), self._imagen(self._estado("parque")))

    def test_el_pin_del_jugador_se_dibuja_encima_de_todo_y_se_ve_en_todos_los_temas(self) -> None:
        """Aunque la zona del jugador tenga algo por descubrir y el camino pase por ella, el pin queda visible."""
        estado = self._estado("plaza", pendientes={"plaza", "colegio"}, ruta=("colegio", "plaza", "alcaldia"),
                              costo_ruta=4, hover="plaza", teclas=True)
        x, y = _posiciones(estado, RECT_MAPA)["plaza"]
        cabeza = (RECT_MAPA.x + x, RECT_MAPA.y + y - RADIO + px(3) - px(22))
        for id, tema in TEMAS.items():
            self._imagen(estado, id)
            self.assertEqual(self.pantalla.get_at(cabeza)[:3], tema.fondo, id)                       # punto central
            self.assertEqual(self.pantalla.get_at((cabeza[0] + px(7), cabeza[1]))[:3], tema.acento, id)   # cuerpo del pin
            self.assertEqual(self.pantalla.get_at((cabeza[0] + px(12), cabeza[1]))[:3], tema.texto, id)   # contorno claro

    def test_el_pin_cambia_de_lugar_con_el_jugador(self) -> None:
        for a, b in (("plaza", "colegio"), ("colegio", "alcaldia"), ("alcaldia", "parque")):
            self.assertNotEqual(self._imagen(self._estado(a)), self._imagen(self._estado(b)))

    def test_la_evidencia_pendiente_y_la_revisada_se_distinguen_por_forma_no_solo_por_color(self) -> None:
        tema = TEMAS["normal"]
        x, y = _posiciones(self._estado(), RECT_MAPA)["alcaldia"]
        region = pygame.Rect(RECT_MAPA.x + x + RADIO - px(14), RECT_MAPA.y + y - RADIO - px(10), px(30), px(30))

        def pintados(estado: EstadoMapa) -> int:
            self._imagen(estado)
            sub = self.pantalla.subsurface(region)
            return sum(sub.get_at((i, j))[:3] != tema.fondo for i in range(region.w) for j in range(region.h))

        nada = pintados(self._estado())
        pendiente = pintados(self._estado(pendientes={"alcaldia"}))
        revisada = pintados(self._estado(revisadas={"alcaldia"}))
        self.assertGreater(pendiente, revisada)             # rombo relleno con "?" vs rombo hueco con visto
        self.assertGreater(revisada, nada)
        self.assertNotEqual(self._imagen(self._estado(pendientes={"alcaldia"})),
                            self._imagen(self._estado(revisadas={"alcaldia"})))

    def test_la_ruta_elegida_se_resalta(self) -> None:
        sin = self._imagen(self._estado())
        con = self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=2))
        otra = self._imagen(self._estado(ruta=("plaza", "parque", "barrio"), costo_ruta=2))
        self.assertEqual(len({sin, con, otra}), 3)

    # --- el jugador no ve el grafo: nada de distancias, cifras ni letras sobre el mapa ---------------
    def test_el_mapa_no_dibuja_distancias_ni_cifras(self) -> None:
        """La distancia de cada via y el costo total de la ruta son calculo interno: cambiarlos no cambia el dibujo."""
        copia = GrafoCiudad.from_dict(self.ciudad.to_dict())
        antes = self._imagen(EstadoMapa(copia, "plaza", ruta=("plaza", "alcaldia"), costo_ruta=2))
        copia.eliminar_conexion("barrio", "plaza")
        copia.agregar_conexion("barrio", "plaza", 7)
        despues = self._imagen(EstadoMapa(copia, "plaza", ruta=("plaza", "alcaldia"), costo_ruta=2))
        self.assertEqual(antes, despues)                    # otra distancia, mismo mapa
        self.assertEqual(self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=2)),
                         self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=9)))   # otro costo total, mismo mapa

    def test_las_zonas_no_llevan_numeros_ni_letras_encima(self) -> None:
        """Sin el mouse encima, mostrar o no los costos y las teclas no cambia el mapa."""
        base = self._imagen(self._estado(energia=5, teclas=False))
        self.assertEqual(base, self._imagen(self._estado(energia=5, teclas=True)))
        self.assertEqual(base, self._imagen(self._estado(energia=None, teclas=False)))

    def test_los_lugares_a_los_que_no_alcanza_la_energia_se_ven_apagados(self) -> None:
        self.assertNotEqual(self._imagen(self._estado(energia=5)), self._imagen(self._estado(energia=1)))
        self.assertEqual(self._imagen(self._estado(energia=5)), self._imagen(self._estado(energia=2)))   # con 2 llega a todo desde la Plaza

    def test_la_franja_de_ayuda_explica_el_viaje_con_rayos_al_pasar_el_mouse(self) -> None:
        sin_mouse = self._imagen(self._estado())
        colegio = self._imagen(self._estado(hover="colegio"))      # cuesta 2
        parque = self._imagen(self._estado(hover="parque"))        # cuesta 1
        self.assertEqual(len({sin_mouse, colegio, parque}), 3)
        # sin energia suficiente el mensaje cambia
        self.assertNotEqual(self._imagen(self._estado(hover="colegio", energia=5)),
                            self._imagen(self._estado(hover="colegio", energia=1)))

    def test_la_tecla_de_atajo_solo_aparece_en_la_franja_de_ayuda(self) -> None:
        self.assertNotEqual(self._imagen(self._estado(hover="colegio", teclas=False)),
                            self._imagen(self._estado(hover="colegio", teclas=True)))

    def test_la_franja_distingue_pendiente_revisado_y_nada(self) -> None:
        imagenes = {self._imagen(self._estado(hover="colegio", **kw))
                    for kw in ({}, {"pendientes": {"colegio"}}, {"revisadas": {"colegio"}})}
        self.assertEqual(len(imagenes), 3)

    def test_sin_franja_el_mapa_ocupa_mas_espacio(self) -> None:
        con = _posiciones(EstadoMapa(self.ciudad, "plaza"), RECT_MAPA)
        sin = _posiciones(EstadoMapa(self.ciudad, "plaza", mostrar_ayuda=False), RECT_MAPA)
        self.assertGreater(sin["barrio"][1], con["barrio"][1])

    def test_los_lugares_no_se_pisan_ni_se_salen_del_mapa(self) -> None:
        for ayuda in (True, False):
            pos = _posiciones(EstadoMapa(self.ciudad, "plaza", mostrar_ayuda=ayuda), RECT_MAPA)
            centros = list(pos.values())
            for i, (x, y) in enumerate(centros):
                self.assertTrue(RECT_MAPA.collidepoint(x, y))
                self.assertGreaterEqual(x - RADIO, RECT_MAPA.x)
                self.assertLessEqual(x + RADIO, RECT_MAPA.right)
                for x2, y2 in centros[i + 1:]:
                    self.assertGreater(((x - x2) ** 2 + (y - y2) ** 2) ** 0.5, 2 * RADIO + px(10))

    def test_colores_del_tema(self) -> None:
        estado = self._estado(pendientes={"colegio"}, ruta=("plaza", "colegio"), costo_ruta=2, hover="colegio")
        self.assertEqual(len({self._imagen(estado, tema) for tema in TEMAS}), 3)

    def test_zona_de_tecla(self) -> None:
        from post_truth.views.mapa_view import tecla_de, zona_de_tecla
        for z in self.ciudad.zonas():
            self.assertEqual(zona_de_tecla(self.ciudad, tecla_de(self.ciudad, z.id)), z.id)
        self.assertIsNone(zona_de_tecla(self.ciudad, "Z"))


if __name__ == "__main__":
    unittest.main()
