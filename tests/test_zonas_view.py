import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import RUTA_GRAFO_CIUDAD
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.mapa_view import EstadoMapa, dibujar_mapa, zona_en
from post_truth.views.theme import TEMAS
from post_truth.views.zona_view import dibujar_fondo_zona

RECT_MAPA = pygame.Rect(0, 0, 270, 262)


class ZonasViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.pantalla = pygame.display.set_mode((1024, 640))
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
        from post_truth.views.mapa_view import _posiciones
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
            self._estado(ruta=ruta.zonas, costo_ruta=ruta.costo, hover="barrio"),
            self._estado(energia=0),                        # todo tachado: no alcanza para ningun viaje
            self._estado("colegio", ruta=("colegio", "plaza"), costo_ruta=2, pendientes={"colegio"}),
            EstadoMapa(self.ciudad, "colegio"),             # el minimo: la introduccion lo usa asi
        ]
        for tema in TEMAS:
            for estado in estados:
                self._imagen(estado, tema)

    def test_la_zona_actual_se_distingue_de_las_demas(self) -> None:
        self.assertNotEqual(self._imagen(self._estado("plaza")), self._imagen(self._estado("parque")))

    def test_el_pin_del_jugador_se_dibuja_encima_de_todo_y_se_ve_en_todos_los_temas(self) -> None:
        """Aunque la zona del jugador tenga evidencia pendiente y la ruta pase por ella, el pin queda visible."""
        from post_truth.views.mapa_view import RADIO, _posiciones
        estado = self._estado("plaza", pendientes={"plaza", "colegio"}, ruta=("colegio", "plaza", "alcaldia"),
                              costo_ruta=4, hover="plaza", teclas=True)
        x, y = _posiciones(estado, RECT_MAPA)["plaza"]
        cabeza = (RECT_MAPA.x + x, RECT_MAPA.y + y - RADIO + 2 - 19)
        for id, tema in TEMAS.items():
            self._imagen(estado, id)
            self.assertEqual(self.pantalla.get_at((cabeza[0], cabeza[1]))[:3], tema.fondo, id)        # punto central
            self.assertEqual(self.pantalla.get_at((cabeza[0] + 7, cabeza[1]))[:3], tema.acento, id)   # cuerpo del pin
            self.assertEqual(self.pantalla.get_at((cabeza[0] + 10, cabeza[1]))[:3], tema.texto, id)   # contorno claro

    def test_la_evidencia_pendiente_y_la_revisada_se_distinguen_por_forma_no_solo_por_color(self) -> None:
        from post_truth.views.mapa_view import RADIO, _posiciones
        tema = TEMAS["normal"]
        x, y = _posiciones(self._estado(), RECT_MAPA)["alcaldia"]
        region = pygame.Rect(RECT_MAPA.x + x + RADIO - 6, RECT_MAPA.y + y - 14, 26, 24)

        def pintados(estado: EstadoMapa) -> int:
            self._imagen(estado)
            sub = self.pantalla.subsurface(region)
            fondo = tema.fondo
            return sum(sub.get_at((i, j))[:3] != fondo for i in range(region.w) for j in range(region.h))

        nada = pintados(self._estado())
        pendiente = pintados(self._estado(pendientes={"alcaldia"}))
        revisada = pintados(self._estado(revisadas={"alcaldia"}))
        self.assertGreater(pendiente, revisada)             # rombo relleno con "?" vs rombo hueco con visto
        self.assertGreater(revisada, nada)
        self.assertNotEqual(self._imagen(self._estado(pendientes={"alcaldia"})),
                            self._imagen(self._estado(revisadas={"alcaldia"})))

    def test_la_ruta_elegida_se_resalta_y_muestra_su_costo(self) -> None:
        sin = self._imagen(self._estado())
        con = self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=2))
        otra = self._imagen(self._estado(ruta=("plaza", "parque", "barrio"), costo_ruta=2))
        self.assertEqual(len({sin, con, otra}), 3)
        self.assertNotEqual(self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=2)),
                            self._imagen(self._estado(ruta=("plaza", "alcaldia"), costo_ruta=7)))   # el numero cambia

    def test_los_costos_de_viaje_dependen_de_la_energia_que_queda(self) -> None:
        self.assertNotEqual(self._imagen(self._estado(energia=5)), self._imagen(self._estado(energia=1)))
        self.assertNotEqual(self._imagen(self._estado(energia=5)), self._imagen(self._estado(energia=None)))

    def test_cada_via_muestra_su_distancia(self) -> None:
        """Cambiar una distancia del grafo cambia el dibujo: el numero sale de los datos, no de la vista."""
        copia = GrafoCiudad.from_dict(self.ciudad.to_dict())    # no se toca el grafo compartido de la clase
        antes = self._imagen(EstadoMapa(copia, "plaza"))
        copia.eliminar_conexion("barrio", "plaza")
        copia.agregar_conexion("barrio", "plaza", 7)
        self.assertNotEqual(antes, self._imagen(EstadoMapa(copia, "plaza")))

    def test_las_letras_de_atajo_aparecen_solo_si_se_pide(self) -> None:
        self.assertNotEqual(self._imagen(self._estado(teclas=False)), self._imagen(self._estado(teclas=True)))

    def test_colores_del_tema(self) -> None:
        estado = self._estado(pendientes={"colegio"}, ruta=("plaza", "colegio"), costo_ruta=2)
        self.assertEqual(len({self._imagen(estado, tema) for tema in TEMAS}), 3)

    def test_zona_de_tecla(self) -> None:
        from post_truth.views.mapa_view import tecla_de, zona_de_tecla
        for z in self.ciudad.zonas():
            self.assertEqual(zona_de_tecla(self.ciudad, tecla_de(self.ciudad, z.id)), z.id)
        self.assertIsNone(zona_de_tecla(self.ciudad, "Z"))


if __name__ == "__main__":
    unittest.main()
