"""Partidas completas jugadas por un bot, sin ventana (SDL dummy).

Recorre el flujo real Menu -> Seleccion -> Escena (decidir, propagacion por el grafo social,
movimiento por el mapa de la ciudad, rumores, Desmentir) -> Fin -> Menu, con eventos de teclado
y de mouse, avanzando el tiempo con dt como lo hace el game loop. Tras cada paso dibuja (rotando
los 3 temas) y comprueba invariantes: si algo se rompe en medio de una partida, falla aqui.
"""
import os
import random
import runpy
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, FIN, PROPAGACION
from post_truth.pygame_app import App
from post_truth.views.escena_view import RECT_MAPA
from post_truth.views.mapa_view import _posiciones

FASES = {DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN}
TECLAS_ROL = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
MAX_PASOS = 400  # tope por partida: si el bot no avanza, es un bloqueo del juego


class Bot:
    def __init__(self, app: App, semilla: int, modo: str = "teclado", politica: str = "azar") -> None:
        self.app, self.modo, self.politica = app, modo, politica
        self.rng = random.Random(semilla)
        self.pasos = 0
        self.ronda_previa = 0

    # --- entrada --------------------------------------------------------------------------
    @property
    def escena(self):
        return self.app.estados._estados["escena"]

    def tecla(self, k: int) -> None:
        self.app.estados.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    def clic(self, pos: tuple[int, int]) -> None:
        manejar = self.app.estados.handle_event
        manejar(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        manejar(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        manejar(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))

    def activar(self, boton) -> None:
        if self.modo == "mouse":
            self.clic(boton.rect.center)
        else:
            assert boton.atajo is not None
            self.tecla(boton.atajo)

    # --- paso a paso con comprobaciones ----------------------------------------------------
    def avanzar(self, dt: float = 1 / 60, dibujar: bool = True) -> None:
        """Un fotograma: update + draw con el tema que toque, y las invariantes."""
        self.pasos += 1
        assert self.pasos < MAX_PASOS * 40, "el bot no logra terminar la partida (bloqueo)"
        self.app.estados.update(dt)
        if self.pasos % 7 == 0:
            self.app.temas.siguiente()
        if dibujar:
            self.app.estados.draw(self.app.pantalla)
        self.invariantes()

    def invariantes(self) -> None:
        e = self.escena
        if self.app.estados._actual is not e:   # en el menu o la seleccion no hay escena que revisar
            return
        if e.fase not in FASES:
            self.fail(f"fase invalida: {e.fase}")
        for nombre, valor in e.ciudad.as_display_rows():
            if not nombre.startswith("Puntaje"):
                assert 0 <= valor <= 100, f"{nombre} fuera de rango: {valor}"
        assert e.zona in e.mapa, f"zona inexistente: {e.zona}"
        assert e.rumores.zonas_infectadas() <= {z.id for z in e.mapa.zonas()}
        assert e.ronda >= self.ronda_previa, "las rondas no pueden retroceder"
        self.ronda_previa = e.ronda
        assert e.dialogo.texto, "la caja de dialogo no puede quedar vacia"
        assert e.botones, f"sin botones en la fase {e.fase}"
        if e.fase == DECIDIENDO:
            assert any(b.habilitado for b in e.botones), "todas las acciones bloqueadas: bloqueo del juego"

    def fail(self, msg: str) -> None:
        raise AssertionError(msg)

    # --- jugar ----------------------------------------------------------------------------
    def empezar(self, rol: int, genero: int) -> None:
        if self.app.estados._actual is not self.app.estados._estados["menu"]:
            self.app.estados.cambiar("menu")
        self.avanzar()
        self.tecla(pygame.K_RETURN)                     # menu -> seleccion
        sel = self.app.estados._actual
        self.activar(sel.botones[rol])                  # rol
        sel = self.app.estados._actual
        assert sel is self.app.estados._estados["seleccion"]
        self.activar(sel.botones[genero])               # hombre (0) / mujer (1)
        assert self.app.estados._actual is self.app.estados._estados["escena"]
        self.avanzar()

    def tipo(self, boton) -> str:
        """Tipo de decision del boton ("compartir", "verificar", ...) o "desmentir" si es el extra."""
        ramas = self.escena.arbol.root.children[:4]
        i = self.escena.botones.index(boton)
        return ramas[i].tipo if i < len(ramas) else "desmentir"

    def elegir(self, habilitados: list) -> object:
        por_tipo = {self.tipo(b): b for b in habilitados}
        if self.politica == "compartir":
            return por_tipo.get("compartir", habilitados[0])
        if self.politica == "ignorar":
            return por_tipo.get("ignorar", habilitados[0])
        if self.politica == "investigar":   # actua con responsabilidad: desmiente y verifica en el lugar
            for tipo in ("desmentir", "verificar", "reportar"):
                if tipo in por_tipo:
                    return por_tipo[tipo]
        return self.rng.choice(habilitados)

    def ir_a_la_zona_de_la_noticia(self) -> bool:
        """Un paso por el camino mas corto (BFS) hacia la zona de la noticia. False si ya esta ahi."""
        e = self.escena
        if e.zona == e.arbol.event.zone:
            return False
        ruta = e.mapa.camino(e.zona, e.arbol.event.zone)
        assert ruta is not None and len(ruta) >= 2, "la noticia esta en una zona inalcanzable"
        self.ir_a(ruta[1])
        return True

    def ir_a(self, destino: str) -> None:
        e = self.escena
        vecinos = e.mapa.vecinos(e.zona)
        if self.modo == "mouse":
            self.clic(_posiciones(e._estado_mapa(), RECT_MAPA)[destino])
        else:
            self.tecla([pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r][vecinos.index(destino)])
        assert e.zona == destino
    def mover(self) -> None:
        e = self.escena
        self.ir_a(self.rng.choice(e.mapa.vecinos(e.zona)))

    def jugar_publicacion(self) -> None:
        e, movimientos = self.escena, 0
        while e.fase == DECIDIENDO:
            if self.politica == "azar" and movimientos < 3 and self.rng.random() < 0.3:
                self.mover()
                movimientos += 1
            elif (self.politica == "investigar" and "desmentir" not in
                  {self.tipo(b) for b in e.botones if b.habilitado} and self.ir_a_la_zona_de_la_noticia()):
                movimientos += 1
            else:
                self.activar(self.elegir([b for b in e.botones if b.habilitado]))
            self.avanzar()
        if e.fase == PROPAGACION:
            self.ver_propagacion()
        assert e.fase == CONSECUENCIA, f"tras decidir se esperaba CONSECUENCIA y hay {e.fase}"
        self.avanzar(0.5)                                # deja correr el texto
        self.activar(e.botones[0])                       # Continuar
        self.avanzar()

    def ver_propagacion(self) -> None:
        e = self.escena
        if self.rng.random() < 0.5:                      # saltar la animacion
            self.activar(e.botones[0])
            self.avanzar()
        else:                                            # verla entera con dt de 60 FPS
            for i in range(60 * 40):
                self.avanzar(1 / 60, dibujar=i % 5 == 0)
                if e.botones[0].texto.startswith("Ver consecuencias"):
                    break
            else:
                self.fail("la animacion de propagacion no termino")
        self.activar(e.botones[0])                       # Ver consecuencias
        self.avanzar()

    def partida(self, rol: int = 0, genero: int = 0) -> None:
        self.empezar(rol, genero)
        e = self.escena
        for _ in range(len(e.arboles)):
            assert e.fase == DECIDIENDO
            self.jugar_publicacion()
        assert e.fase == FIN, f"la partida debia terminar y esta en {e.fase}"
        self.activar(e.botones[0])                       # Volver al menu
        assert self.app.estados._actual is self.app.estados._estados["menu"]


class PartidaCompletaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.app.intro_vista = True   # estas pruebas empiezan en Menu -> Seleccion

    def tearDown(self) -> None:
        pygame.quit()

    def test_partida_completa_con_cada_rol_y_genero(self) -> None:
        for rol in range(4):
            for genero in range(2):
                Bot(self.app, semilla=rol * 10 + genero).partida(rol, genero)
                self.assertEqual(self.app.personaje.rol, list(self.app.personaje.rol.__class__)[rol])

    def test_partida_completa_solo_con_mouse(self) -> None:
        for semilla in range(6):
            Bot(self.app, semilla, modo="mouse").partida(semilla % 4, semilla % 2)

    def test_muchas_partidas_seguidas_con_azar(self) -> None:
        """40 partidas distintas en la misma App: cada una arranca limpia de la anterior."""
        for semilla in range(40):
            bot = Bot(self.app, semilla, modo="mouse" if semilla % 3 == 0 else "teclado")
            bot.partida(semilla % 4, semilla % 2)
            self.assertEqual(self.escena_inicial_limpia(), (True, True, True))
            tras = self.app.estados._estados["escena"]
            self.assertIs(self.app.estados._actual, self.app.estados._estados["menu"])
            self.assertGreaterEqual(tras.ronda, 0)

    def escena_inicial_limpia(self) -> tuple[bool, bool, bool]:
        """Entrar de nuevo a la escena reinicia ciudad, rumores y zona."""
        e = self.app.estados._estados["escena"]
        self.app.estados.cambiar("escena")
        res = (e.ronda == 0, e.zona == e.mapa.zona_inicial and not e.rumores.zonas_infectadas(),
               e.ciudad.score == 0 and e.fase == DECIDIENDO)
        self.app.estados.cambiar("menu")
        return res

    def test_politica_de_solo_ignorar_deja_crecer_los_rumores_sin_romper_nada(self) -> None:
        for rol in range(4):
            Bot(self.app, 100 + rol, politica="ignorar").partida(rol, 0)
        e = self.app.estados._estados["escena"]
        self.assertLessEqual(e.ciudad.misinformation, 100)

    def test_politica_de_solo_compartir_llega_a_los_topes_sin_salirse_de_rango(self) -> None:
        for rol in range(4):
            Bot(self.app, 200 + rol, politica="compartir").partida(rol, 1)

    def test_investigar_viaja_por_el_camino_mas_corto_y_deja_la_ciudad_sin_rumores(self) -> None:
        for rol in range(4):
            bot = Bot(self.app, 300 + rol, politica="investigar", modo="mouse" if rol % 2 else "teclado")
            bot.partida(rol, 0)
            e = bot.escena
            self.assertEqual(e.rumores.activos(), [], "quedaron rumores sin atender")
            self.assertLess(e.ciudad.misinformation, 100)

    def test_la_habilidad_importa_investigar_supera_a_ignorar(self) -> None:
        """Mismas condiciones (rol y semilla): quien investiga y verifica termina con mejor puntaje
        y menos desinformacion que quien ignora todo."""
        puntaje = {"investigar": 0, "ignorar": 0}
        desinfo = {"investigar": 0, "ignorar": 0}
        for politica in puntaje:
            for semilla in range(8):
                bot = Bot(self.app, semilla, politica=politica)
                bot.partida(semilla % 4, 0)
                puntaje[politica] += bot.escena.ciudad.score
                desinfo[politica] += bot.escena.ciudad.misinformation
        self.assertGreater(puntaje["investigar"], puntaje["ignorar"])
        self.assertLess(desinfo["investigar"], desinfo["ignorar"])

    def test_esc_en_cualquier_fase_vuelve_al_menu_y_la_siguiente_partida_es_limpia(self) -> None:
        for fase_objetivo in (DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN):
            bot = Bot(self.app, 7, politica="compartir")
            bot.empezar(2, 1)
            e = bot.escena
            n = len(e.arboles)
            if fase_objetivo == FIN:
                for _ in range(n):
                    bot.jugar_publicacion()
            elif fase_objetivo in (PROPAGACION, CONSECUENCIA):
                bot.activar(bot.elegir([b for b in e.botones if b.habilitado]))
                if fase_objetivo == CONSECUENCIA:
                    bot.ver_propagacion()
            self.assertEqual(e.fase, fase_objetivo)
            bot.tecla(pygame.K_ESCAPE)
            self.assertIs(self.app.estados._actual, self.app.estados._estados["menu"])
            Bot(self.app, 8).partida(0, 0)                       # y se puede volver a jugar completo

    def test_el_game_loop_real_ejecuta_la_partida(self) -> None:
        """App.run() con reloj real: se encolan los eventos de una partida corta y un QUIT diferido."""
        post = pygame.event.post
        for k in (pygame.K_RETURN, pygame.K_1, pygame.K_2, pygame.K_1):  # menu, rol, genero, primera decision
            post(pygame.event.Event(pygame.KEYDOWN, key=k))
        pygame.time.set_timer(pygame.QUIT, 400, loops=1)               # cierra solo tras ~24 fotogramas
        self.app.run()                                                  # run() llama a pygame.quit() al salir
        self.assertFalse(self.app.corriendo)
        self.app = App()                                                # tearDown vuelve a hacer quit()

    def test_el_punto_de_entrada_src_main_py_arranca_y_cierra(self) -> None:
        """Ejecuta src/main.py tal cual (como `python src/main.py`) y lo cierra con un QUIT diferido."""
        pygame.time.set_timer(pygame.QUIT, 300, loops=1)
        runpy.run_path(str(Path(__file__).resolve().parents[1] / "src" / "main.py"), run_name="__main__")
        self.app = App()

    def test_arrancar_cierra_con_el_evento_quit_desde_el_menu(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        self.app.run()
        self.assertFalse(self.app.corriendo)
        self.app = App()


if __name__ == "__main__":
    unittest.main()
