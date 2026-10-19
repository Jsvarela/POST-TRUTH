"""Administrador de pantallas: delega eventos/update/draw en el estado activo.

FUNDIDO (entrar y salir de un lugar del mundo): `cambiar(nombre, fundido=True)` oscurece el estado actual durante
DURACION_FUNDIDO, cambia de estado en el punto mas oscuro y aclara el nuevo durante otro DURACION_FUNDIDO.
Mientras dura se ignoran las teclas (nada de doble E ni ESC a mitad de camino) y el estado que se va queda
congelado. El tiempo corre con dt, como todo lo demas.
"""
from typing import Callable

import pygame

from post_truth.controllers.base_state import BaseState

DURACION_FUNDIDO = 0.2   # segundos de cada mitad (oscurecer y aclarar)


class StateManager:
    def __init__(self, color_fundido: Callable[[], tuple[int, int, int]] = lambda: (0, 0, 0)) -> None:
        self._estados: dict[str, BaseState] = {}
        self._actual: BaseState | None = None
        self._color_fundido = color_fundido    # del tema activo (lo pasa la App)
        self._fase: str | None = None          # None | "salida" | "entrada"
        self._t = 0.0
        self._destino = ""

    def registrar(self, nombre: str, estado: BaseState) -> None:
        self._estados[nombre] = estado

    def cambiar(self, nombre: str, fundido: bool = False) -> None:
        if fundido and self._actual is not None:
            self._destino, self._fase, self._t = nombre, "salida", 0.0
            return
        self._fase = None
        self._actual = self._estados[nombre]
        self._actual.al_entrar()

    @property
    def en_fundido(self) -> bool:
        return self._fase is not None

    @property
    def opacidad_fundido(self) -> float:
        """0 transparente .. 1 tapa todo."""
        if self._fase == "salida":
            return min(1.0, self._t / DURACION_FUNDIDO)
        if self._fase == "entrada":
            return max(0.0, 1 - self._t / DURACION_FUNDIDO)
        return 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._actual and not self.en_fundido:
            self._actual.handle_event(event)

    def update(self, dt: float) -> None:
        if self._fase == "salida":
            self._t += dt
            if self._t >= DURACION_FUNDIDO:          # punto mas oscuro: aqui cambia el estado
                self._actual = self._estados[self._destino]
                self._actual.al_entrar()
                self._fase, self._t = "entrada", 0.0
            return                                     # el estado que se va queda congelado
        if self._fase == "entrada":
            self._t += dt
            if self._t >= DURACION_FUNDIDO:
                self._fase = None
        if self._actual:
            self._actual.update(dt)

    def draw(self, pantalla: pygame.Surface) -> None:
        if self._actual:
            self._actual.draw(pantalla)
        opacidad = self.opacidad_fundido
        if opacidad > 0:
            velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
            velo.fill((*self._color_fundido(), round(255 * opacidad)))
            pantalla.blit(velo, (0, 0))
