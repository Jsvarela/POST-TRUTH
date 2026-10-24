"""Administrador de pantallas: delega eventos/update/draw en el estado activo."""
from typing import Callable

import pygame

from post_truth.controllers.base_state import BaseState

DURACION_FUNDIDO = 0.2


class StateManager:
    def __init__(self, color_fundido: Callable[[], tuple[int, int, int]] = lambda: (0, 0, 0)) -> None:   # App pasa el del tema: no es un color
        self._estados: dict[str, BaseState] = {}
        self._actual: BaseState | None = None
        self._color_fundido = color_fundido
        self._fase: str | None = None
        self._t = 0.0
        self._destino = ""
        self.capa = None   # capa global encima de todo (HUD compacto y textos flotantes)
        self.sustentacion = None   # modo sustentacion (F1): tapa todo y pausa la pantalla de abajo

    def registrar(self, nombre: str, estado: BaseState) -> None:
        self._estados[nombre] = estado

    @property
    def actual(self) -> BaseState | None:
        return self._actual

    def estado(self, nombre: str) -> BaseState:
        return self._estados[nombre]

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
        """Opacidad del fundido, de 0 a 1."""
        if self._fase == "salida":
            return min(1.0, self._t / DURACION_FUNDIDO)
        if self._fase == "entrada":
            return max(0.0, 1 - self._t / DURACION_FUNDIDO)
        return 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        s = self.sustentacion
        if s is not None and (s.activo or (event.type == pygame.KEYDOWN and event.key == pygame.K_F1)):
            if s.activo:
                s.handle_event(event)
            else:
                s.alternar()
            return
        if self._actual and not self.en_fundido:
            self._actual.handle_event(event)

    def update(self, dt: float) -> None:
        if self.sustentacion is not None and self.sustentacion.activo:
            return
        if self._fase == "salida":
            self._t += dt
            if self._t >= DURACION_FUNDIDO:
                self._actual = self._estados[self._destino]
                self._actual.al_entrar()
                self._fase, self._t = "entrada", 0.0
            return
        if self._fase == "entrada":
            self._t += dt
            if self._t >= DURACION_FUNDIDO:
                self._fase = None
        if self._actual:
            self._actual.update(dt)
        if self.capa is not None:
            self.capa.update(dt, self._actual)

    def draw(self, pantalla: pygame.Surface) -> None:
        if self._actual:
            self._actual.draw(pantalla)
            if self.capa is not None:
                self.capa.draw(pantalla, self._actual)
        opacidad = self.opacidad_fundido
        if opacidad > 0:
            velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
            velo.fill((*self._color_fundido(), round(255 * opacidad)))
            pantalla.blit(velo, (0, 0))
        if self.sustentacion is not None and self.sustentacion.activo:
            self.sustentacion.draw(pantalla)
