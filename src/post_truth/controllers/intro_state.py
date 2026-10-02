"""Controlador de la introduccion: pasa las laminas con fundidos y texto letra por letra.

Cada lamina recorre tres fases, todas medidas con `dt` (nunca con sleep, el loop sigue a 60 FPS):
    ENTRANDO     la lamina aparece con un fundido (FADE_ENTRADA s)
    MANTENIENDO  se queda hasta que el jugador avanza
    SALIENDO     fundido de salida (FADE_SALIDA s) y se carga la siguiente

Controles: clic o cualquier tecla (menos ESC) avanzan; si el subtitulo aun se esta escribiendo, el
primer clic lo completa y el siguiente avanza (como en una novela visual). ESC salta toda la
introduccion. Al terminar o saltar, el juego sigue a la seleccion de personaje.
"""
import pygame

from post_truth.config import ANCHO, RUTA_GRAFO_CIUDAD, RUTA_INTRO, px
from post_truth.controllers.base_state import BaseState
from post_truth.models.intro import Intro
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import CajaDialogo
from post_truth.views.intro_view import TAMANO_LIENZO, dibujar_intro

ENTRANDO, MANTENIENDO, SALIENDO = "entrando", "manteniendo", "saliendo"
FADE_ENTRADA, FADE_SALIDA = 0.7, 0.5
CARACTERES_POR_SEGUNDO = 45.0
RECT_SUBTITULO = pygame.Rect(px(24), px(492), ANCHO - 2 * px(24), px(116))   # debajo del dibujo (ver intro_view.ALTO_ARTE)
PIE = "Clic o tecla: continuar   |   ESC: saltar la introduccion"


class IntroState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.intro = Intro.cargar(RUTA_INTRO)
        self.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)  # el mapa de la lamina de zonas
        self.dialogo = CajaDialogo(RECT_SUBTITULO, CARACTERES_POR_SEGUNDO)
        self.lienzo = pygame.Surface(TAMANO_LIENZO)           # se reutiliza: no se crea uno por fotograma
        self.indice = 0
        self.fase = ENTRANDO
        self.t = 0.0           # segundos desde que empezo la lamina (anima el dibujo)
        self._t_salida = 0.0   # segundos desde que empezo el fundido de salida

    @property
    def lamina(self):
        return self.intro.laminas[self.indice]

    @property
    def alfa(self) -> float:
        """Opacidad 0..255 del dibujo (el subtitulo no se desvanece nunca)."""
        if self.fase == ENTRANDO:
            return 255 * min(1.0, self.t / FADE_ENTRADA)
        if self.fase == SALIENDO:
            return 255 * max(0.0, 1.0 - self._t_salida / FADE_SALIDA)
        return 255.0

    def al_entrar(self) -> None:
        self.indice = 0
        self._cargar_lamina()

    # --- secuencia -----------------------------------------------------------------------
    def _cargar_lamina(self) -> None:
        self.fase, self.t, self._t_salida = ENTRANDO, 0.0, 0.0
        self.dialogo.set_texto(self.lamina.texto, self.lamina.titulo)

    def avanzar(self) -> None:
        """Clic o tecla: completa el subtitulo si aun se escribe; si no, pasa a la siguiente lamina."""
        if self.fase == SALIENDO:
            return                      # ya esta cambiando de lamina: ignora clics repetidos
        if not self.dialogo.terminado:
            self.dialogo.completar()
            return
        self.fase, self._t_salida = SALIENDO, 0.0

    def saltar(self) -> None:
        """ESC: termina la introduccion de inmediato."""
        self._terminar()

    def _siguiente(self) -> None:
        self.indice += 1
        if self.indice >= len(self.intro.laminas):
            self._terminar()
        else:
            self._cargar_lamina()

    def _terminar(self) -> None:
        self.app.intro_vista = True     # desde ahora ENTER en el menu va directo a la seleccion
        self.app.estados.cambiar("seleccion")

    # --- ciclo del estado ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.saltar()
            else:
                self.avanzar()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.avanzar()

    def update(self, dt: float) -> None:
        self.dialogo.update(dt)
        self.t += dt
        if self.fase == ENTRANDO and self.t >= FADE_ENTRADA:
            self.fase = MANTENIENDO
        elif self.fase == SALIENDO:
            self._t_salida += dt
            if self._t_salida >= FADE_SALIDA:
                self._siguiente()

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_intro(pantalla, self.lienzo, self.app.fuentes, self.app.temas.actual, self.intro, self.ciudad,
                      self.indice, self.t, self.alfa, self.dialogo, PIE)
