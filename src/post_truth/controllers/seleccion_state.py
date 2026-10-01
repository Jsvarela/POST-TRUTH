"""Controlador de la seleccion: primero el ROL y luego el personaje (hombre o mujer).

Es un unico estado con dos fases (en vez de dos estados) porque comparten el resultado
parcial (el rol elegido) y ESC solo debe retroceder una fase.
"""
import pygame

from post_truth.config import ANCHO, ALTO
from post_truth.controllers.base_state import BaseState
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.componentes import Boton, Panel
from post_truth.views.seleccion_view import dibujar_seleccion

FASE_ROL, FASE_GENERO = "rol", "genero"
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]


class SeleccionState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.fase = FASE_ROL
        self.rol: Role | None = None
        self.botones: list[Boton] = []
        self._construir()

    def al_entrar(self) -> None:
        self.fase, self.rol = FASE_ROL, None
        self._construir()

    # --- construccion de la pantalla segun la fase -------------------------------------
    def _construir(self) -> None:
        if self.fase == FASE_ROL:
            self.botones = [
                Boton(pygame.Rect(60, 140 + i * 88, 340, 64), f"{i + 1}. {rol.value}",
                      lambda r=rol: self._elegir_rol(r), atajo=ATAJOS[i])
                for i, rol in enumerate(Role)
            ]
        else:
            self.botones = [
                Boton(pygame.Rect(130 + 60, 450, 240, 56), "1. Hombre",
                      lambda: self._elegir_genero(Genero.HOMBRE), atajo=pygame.K_1),
                Boton(pygame.Rect(534 + 60, 450, 240, 56), "2. Mujer",
                      lambda: self._elegir_genero(Genero.MUJER), atajo=pygame.K_2),
                Boton(pygame.Rect(30, ALTO - 84, 160, 50), "Volver", self._volver),
            ]

    def _elegir_rol(self, rol: Role) -> None:
        self.rol, self.fase = rol, FASE_GENERO
        self._construir()

    def _elegir_genero(self, genero: Genero) -> None:
        assert self.rol is not None
        self.app.personaje = Personaje(self.rol, genero)  # lo leera la escena
        self.app.estados.cambiar("escena")

    def _volver(self) -> None:
        if self.fase == FASE_GENERO:
            self.fase, self.rol = FASE_ROL, None
            self._construir()
        else:
            self.app.estados.cambiar("menu")

    # --- ciclo del estado ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._volver()
            return
        for boton in list(self.botones):  # copia: un clic reconstruye self.botones
            if boton.handle_event(event):
                break

    def update(self, dt: float) -> None:
        pass  # sin animaciones temporizadas en esta pantalla

    def draw(self, pantalla: pygame.Surface) -> None:
        fuentes, tema = self.app.fuentes, self.app.temas.actual
        if self.fase == FASE_ROL:
            # La vista previa sigue al mouse (hover); si no hay hover, muestra el primer rol.
            idx = next((i for i, b in enumerate(self.botones) if b.hover), 0)
            rol = list(Role)[idx]
            panel = Panel(pygame.Rect(440, 130, 544, 420), rol.value)
            ejemplo = Personaje(rol, Genero.HOMBRE)  # la vista previa del rol; el genero se elige luego
            dibujar_seleccion(
                pantalla, fuentes, tema, "Elige tu rol", "Cada rol decide distinto en Civitas",
                [panel], [(ejemplo, pygame.Rect(470, 190, 190, 330))],
                (pygame.Rect(680, 190, 280, 300), ejemplo.descripcion_rol),
                self.botones, "Clic o teclas 1-4  |  ESC: volver")
        else:
            assert self.rol is not None
            paneles = [Panel(pygame.Rect(130, 130, 360, 400)), Panel(pygame.Rect(534, 130, 360, 400))]
            previas = [
                (Personaje(self.rol, Genero.HOMBRE), pygame.Rect(160, 150, 300, 290)),
                (Personaje(self.rol, Genero.MUJER), pygame.Rect(564, 150, 300, 290)),
            ]
            dibujar_seleccion(
                pantalla, fuentes, tema, "Elige tu personaje", f"Rol: {self.rol.value}",
                paneles, previas, None, self.botones, "Clic o teclas 1-2  |  ESC: volver")
