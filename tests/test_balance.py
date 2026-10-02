"""Balance del juego medido con el bot (tools/balance.py): reproducibilidad, invariantes y orden entre politicas.

No fija cifras exactas (eso lo hace la tabla de docs/entrega2_grafos.md): comprueba la FORMA del balance, con
suficientes partidas para que el azar no la voltee. Si alguien cambia FUERZA_*, la energia o los topes de
propagacion y el juego se vuelve trivial o imposible, falla aqui.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))

import pygame

import balance
from post_truth.config import EVENTOS_POR_PARTIDA
from post_truth.pygame_app import App

PARTIDAS = 80    # por politica y rol: unos segundos


class BalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tablas = {rol: balance.medir(PARTIDAS, rol) for rol in (0, 2)}   # Ciudadano e Influencer

    def test_compartir_o_ignorar_siempre_pierde(self) -> None:
        for rol, t in self.tablas.items():
            self.assertLessEqual(t["compartir"]["gana_pct"], 5, rol)
            self.assertLessEqual(t["ignorar"]["gana_pct"], 15, rol)
            self.assertGreater(t["compartir"]["desinformacion"], 80, rol)      # la ciudad se llena de rumores
            self.assertGreater(t["ignorar"]["desinformacion"], 60, rol)

    def test_investigar_con_criterio_gana_la_mayoria_pero_no_todas(self) -> None:
        for rol, t in self.tablas.items():
            self.assertGreaterEqual(t["investigar"]["gana_pct"], 70, rol)
            self.assertLessEqual(t["investigar"]["gana_pct"], 97, rol)

    def test_verificar_a_ciegas_queda_en_medio(self) -> None:
        for rol, t in self.tablas.items():
            self.assertGreater(t["verificar"]["gana_pct"], t["ignorar"]["gana_pct"] + 15, rol)
            self.assertLess(t["verificar"]["gana_pct"], t["investigar"]["gana_pct"] - 15, rol)

    def test_el_orden_de_las_politicas_en_desinformacion_y_puntaje(self) -> None:
        for rol, t in self.tablas.items():
            orden = sorted(t, key=lambda p: t[p]["desinformacion"])
            self.assertEqual(orden[0], "investigar", rol)                      # la que menos desinformacion deja
            self.assertEqual(orden[-1], "compartir", rol)                      # y la que mas
            self.assertLess(t["verificar"]["desinformacion"], t["ignorar"]["desinformacion"], rol)
            puntaje = {p: v["puntaje"] for p, v in t.items()}
            self.assertEqual(max(puntaje, key=puntaje.get), "investigar", rol)

    def test_mismas_semillas_dan_la_misma_tabla(self) -> None:
        self.assertEqual(balance.medir(10, 0), balance.medir(10, 0))

    def test_los_indicadores_terminan_entre_0_y_100_y_la_partida_tiene_las_publicaciones_previstas(self) -> None:
        app = App()
        try:
            for politica in balance.POLITICAS:
                for semilla in range(12):
                    ciudad = balance.jugar(app, politica, semilla, rol=semilla % 4)
                    for nombre, valor in ciudad.as_display_rows():
                        if not nombre.startswith("Puntaje"):
                            self.assertTrue(0 <= valor <= 100, f"{politica}/{semilla}: {nombre}={valor}")
                    self.assertEqual(len(app.estados._estados["escena"].arboles), EVENTOS_POR_PARTIDA)
        finally:
            pygame.quit()

    def test_el_respaldo_importa_con_mas_pruebas_verificar_rinde_mas(self) -> None:
        from post_truth.structures.propagacion import FUERZA_REPORTAR, FUERZA_VERIFICAR
        self.assertLess(FUERZA_VERIFICAR[0], FUERZA_VERIFICAR[1])
        self.assertLess(FUERZA_VERIFICAR[1], FUERZA_VERIFICAR[2])
        self.assertEqual(FUERZA_REPORTAR[0], 0.0)
        self.assertLess(FUERZA_REPORTAR[1], FUERZA_REPORTAR[2])
        self.assertLess(FUERZA_VERIFICAR[0], 0.3)      # verificar a ciegas no es una ruta facil a la victoria


if __name__ == "__main__":
    unittest.main()
