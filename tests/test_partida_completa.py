"""Partidas completas jugadas por un bot, sin ventana (SDL dummy).

Recorre el flujo real Menu -> Seleccion -> Escena (decidir, propagacion por el grafo social, viajes
por el mapa ponderado de la ciudad, evidencia por zona, pistas de la tarjeta y energia) -> Fin -> Menu,
con eventos de teclado y de mouse, avanzando el tiempo con dt como lo hace el game loop. Tras cada paso dibuja (rotando
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
from post_truth.views.escena_view import RECT_MAPA, RECT_TARJETA
from post_truth.views.mapa_view import _posiciones, tecla_de
from post_truth.views.tarjeta_civitas_view import _layout as _layout_tarjeta

FASES = {DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN}
TECLAS_ROL = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
MAX_PASOS = 400  # tope por partida: si el bot no avanza, es un bloqueo del juego


class Bot:
    def __init__(self, app: App, semilla: int, modo: str = "teclado", politica: str = "azar") -> None:
        self.app, self.modo, self.politica = app, modo, politica
        self.rng = random.Random(semilla)
        self.pasos = 0
        self.viajes = 0       # viajes que de verdad se hicieron
        self.pistas = 0       # pistas de la tarjeta que se revisaron

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
        assert e.dialogo.texto, "la caja de dialogo no puede quedar vacia"
        inv = e.investigacion
        assert 0 <= inv.energia <= inv.energia_max, f"energia fuera de rango: {inv.energia}"
        ids = {p.id for p in inv.pistas} | {ev.id for ev in inv.evidencias}
        assert set(inv.descubiertas) <= ids, "hallazgos descubiertos desconocidos"
        # La energia es una sola: lo gastado en pistas de la tarjeta + en viajes + lo que queda = el total
        en_pistas = sum(inv.pista(id).costo for id in inv.descubiertas if id in {p.id for p in inv.pistas})
        assert en_pistas + inv.viaje_gastado + inv.energia == inv.energia_max, "la energia no cuadra"
        assert inv.lugares_revisados().isdisjoint(inv.lugares_pendientes())
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
        self.tecla(pygame.K_RETURN)                     # menu -> seleccion (o -> intro la primera vez)
        intro = self.app.estados._estados["intro"]
        while self.app.estados._actual is intro:        # pasa la introduccion con clics y dt reales
            self.clic((500, 250))
            for f in range(12):
                self.avanzar(1 / 60, dibujar=f == 0)
        sel = self.app.estados._actual
        self.activar(sel.botones[rol])                  # rol
        sel = self.app.estados._actual
        assert sel is self.app.estados._estados["seleccion"]
        self.activar(sel.botones[genero])               # hombre (0) / mujer (1)
        assert self.app.estados._actual is self.app.estados._estados["escena"]
        self.avanzar()

    def tipo(self, boton) -> str:
        """Tipo de decision del boton ("compartir", "verificar", ...)."""
        return self.escena.arbol.root.children[:4][self.escena.botones.index(boton)].tipo

    def investigar_pistas(self, max_pistas: int | None = None) -> None:
        """Gasta energia en las pistas mas baratas de la tarjeta, con clic o con su letra."""
        e = self.escena
        hechas = 0
        for pista in sorted(e.investigacion.pistas, key=lambda x: x.costo):
            if max_pistas is not None and hechas >= max_pistas:
                break
            if e.investigacion.energia < pista.costo or e.investigacion.esta_descubierta(pista.id):
                continue
            if self.modo == "mouse":
                self.clic(_layout_tarjeta(RECT_TARJETA)[pista.zona].center)
            else:
                letra = "ASDFG"[e.investigacion.pistas.index(pista)]
                self.tecla({"A": pygame.K_a, "S": pygame.K_s, "D": pygame.K_d, "F": pygame.K_f, "G": pygame.K_g}[letra])
            assert e.investigacion.esta_descubierta(pista.id), "la pista debia revelarse (alcanzaba la energia)"
            hechas += 1
            self.pistas += 1
            self.avanzar(dibujar=False)

    def ir_a(self, destino: str) -> bool:
        """Viaja a `destino` con clic en el mapa o con su letra (Q W E R T). Comprueba que se mueva
        solo si alcanza la energia y que cobre exactamente el costo del camino mas corto."""
        e = self.escena
        if destino == e.zona:
            return False
        costo = e.mapa.ruta(e.zona, destino).costo
        energia = e.investigacion.energia
        alcanzaba = costo <= energia
        if self.modo == "mouse":
            self.clic(_posiciones(e._estado_mapa(), RECT_MAPA)[destino])
        else:
            self.tecla({"Q": pygame.K_q, "W": pygame.K_w, "E": pygame.K_e, "R": pygame.K_r,
                        "T": pygame.K_t}[tecla_de(e.mapa, destino)])
        assert (e.zona == destino) == alcanzaba, "el viaje debia ocurrir solo si alcanza la energia"
        assert e.investigacion.energia == energia - (costo if alcanzaba else 0), "el viaje cobro mal"
        if alcanzaba:
            self.viajes += 1
        self.avanzar(dibujar=False)
        return alcanzaba

    def mover_al_azar(self) -> None:
        e = self.escena
        self.ir_a(self.rng.choice([z.id for z in e.mapa.zonas() if z.id != e.zona]))

    def viajar_a_evidencia(self) -> bool:
        """Va a la zona con evidencia pendiente MAS BARATA de las que alcanza la energia."""
        e = self.escena
        costos = e.mapa.costos_desde(e.zona)
        posibles = [z for z in e.investigacion.lugares_pendientes() if 0 < costos[z] <= e.investigacion.energia]
        if not posibles:
            return False
        return self.ir_a(min(posibles, key=lambda z: (costos[z], z)))

    def agotar_la_energia(self) -> None:
        """Gasta TODA la energia (el viaje mas largo posible y todas las pistas baratas) para comprobar que
        con energia 0 el jugador no se queda sin opciones."""
        e = self.escena
        costos = e.mapa.costos_desde(e.zona)
        alcanzables = [z for z, c in costos.items() if 0 < c <= e.investigacion.energia]
        if alcanzables:
            self.ir_a(max(alcanzables, key=lambda z: (costos[z], z)))
        self.investigar_pistas()
        while e.investigacion.energia > 0:               # lo que sobre, en viajes de 1
            vecinos = [z for z, c in e.mapa.costos_desde(e.zona).items() if c == 1]
            if not vecinos or not self.ir_a(vecinos[0]):
                break

    def elegir(self, habilitados: list) -> object:
        por_tipo = {self.tipo(b): b for b in habilitados}
        if self.politica == "compartir":
            return por_tipo.get("compartir", habilitados[0])
        if self.politica == "ignorar":
            return por_tipo.get("ignorar", habilitados[0])
        if self.politica in ("investigar", "informado", "agotar"):
            primero: dict[str, object] = {}
            for b in habilitados:
                primero.setdefault(self.tipo(b), b)
            inv = self.escena.investigacion
            if self.politica == "informado" and inv.veredicto() == "verdadera" and "compartir" in primero:
                return primero["compartir"]            # una noticia cierta se comparte
            if "reportar" in primero and inv.respaldo("reportar") >= 1:
                return primero["reportar"]             # reportar solo con pruebas de falsedad
            for tipo in ("verificar", "reportar", "ignorar"):
                if tipo in primero:
                    return primero[tipo]
        return self.rng.choice(habilitados)

    def jugar_publicacion(self) -> None:
        e = self.escena
        assert e.fase == DECIDIENDO
        if self.politica == "investigar":                # evidencia de campo primero (la mas barata) y pistas con lo que sobre
            self.viajar_a_evidencia()
            self.investigar_pistas(max_pistas=2)
        elif self.politica == "informado":               # tarjeta primero; si apunta a falsa, se busca evidencia de campo
            self.investigar_pistas(max_pistas=2)
            if e.investigacion.veredicto() != "verdadera":
                self.viajar_a_evidencia()
        elif self.politica == "agotar":
            self.agotar_la_energia()
            assert e.investigacion.energia >= 0
        elif self.politica == "azar":                    # explora un poco, sin criterio
            for _ in range(self.rng.randint(0, 2)):
                self.mover_al_azar()
            self.investigar_pistas(max_pistas=self.rng.randint(0, 2))
        self.activar(self.elegir(list(e.botones)))
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

    def test_partida_completa_desde_cero_con_la_introduccion(self) -> None:
        """Menu -> Intro -> Seleccion -> Escena -> Fin -> Menu, con la introduccion incluida."""
        self.app.intro_vista = False
        for modo in ("teclado", "mouse"):
            self.app.intro_vista = False
            Bot(self.app, 77, modo=modo).partida(1, 1)
            self.assertTrue(self.app.intro_vista)

    def test_partida_completa_solo_con_mouse(self) -> None:
        for semilla in range(6):
            Bot(self.app, semilla, modo="mouse").partida(semilla % 4, semilla % 2)

    def test_muchas_partidas_seguidas_con_azar(self) -> None:
        """40 partidas distintas en la misma App: cada una arranca limpia de la anterior."""
        for semilla in range(40):
            bot = Bot(self.app, semilla, modo="mouse" if semilla % 3 == 0 else "teclado")
            bot.partida(semilla % 4, semilla % 2)
            self.assertEqual(self.escena_inicial_limpia(), (True, True, True))
            self.assertIs(self.app.estados._actual, self.app.estados._estados["menu"])

    def escena_inicial_limpia(self) -> tuple[bool, bool, bool]:
        """Entrar de nuevo a la escena reinicia ciudad, posicion y energia."""
        e = self.app.estados._estados["escena"]
        self.app.estados.cambiar("escena")
        res = (e.zona == e.mapa.zona_inicial,
               e.investigacion.energia == e.investigacion.energia_max and e.investigacion.viaje_gastado == 0,
               e.ciudad.score == 0 and e.fase == DECIDIENDO)
        self.app.estados.cambiar("menu")
        return res

    def test_politica_de_solo_ignorar_no_rompe_nada(self) -> None:
        for rol in range(4):
            Bot(self.app, 100 + rol, politica="ignorar").partida(rol, 0)
        e = self.app.estados._estados["escena"]
        self.assertLessEqual(e.ciudad.misinformation, 100)

    def test_politica_de_solo_compartir_llega_a_los_topes_sin_salirse_de_rango(self) -> None:
        for rol in range(4):
            Bot(self.app, 200 + rol, politica="compartir").partida(rol, 1)

    def test_investigar_viaja_a_la_evidencia_mas_barata_y_decide_con_respaldo(self) -> None:
        for rol in range(4):
            bot = Bot(self.app, 300 + rol, politica="investigar", modo="mouse" if rol % 2 else "teclado")
            bot.partida(rol, 0)
            self.assertGreater(bot.viajes, 0, "el bot debia viajar a buscar evidencia")
            self.assertLess(bot.escena.ciudad.misinformation, 100)

    def test_sin_energia_el_jugador_sigue_teniendo_todas_las_opciones(self) -> None:
        """Se gasta TODA la energia de cada publicacion y aun asi se puede decidir y la partida termina."""
        for rol in range(4):
            bot = Bot(self.app, 600 + rol, politica="agotar", modo="mouse" if rol % 2 else "teclado")
            bot.partida(rol, 1)
            self.assertGreater(bot.viajes + bot.pistas, 0)

    def test_partida_informada_investiga_las_pistas_y_decide_con_ellas(self) -> None:
        for rol in range(4):
            bot = Bot(self.app, 400 + rol, politica="informado", modo="mouse" if rol % 2 else "teclado")
            bot.partida(rol, 0)
            self.assertGreater(bot.pistas, 0, "el bot debia revisar pistas de la tarjeta")

    def test_investigar_las_pistas_antes_de_decidir_supera_a_ignorar_y_al_azar(self) -> None:
        puntaje = {"informado": 0, "ignorar": 0, "azar": 0}
        for politica in puntaje:
            for semilla in range(8):
                bot = Bot(self.app, 500 + semilla, politica=politica)
                bot.partida(semilla % 4, 0)
                puntaje[politica] += bot.escena.ciudad.score
        self.assertGreater(puntaje["informado"], puntaje["ignorar"])
        self.assertGreater(puntaje["informado"], puntaje["azar"])

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
