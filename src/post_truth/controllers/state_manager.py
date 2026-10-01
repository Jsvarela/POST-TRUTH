"""Administrador de pantallas: delega eventos/update/draw en el estado activo."""
import pygame
from post_truth.controllers.base_state import BaseState


class StateManager:
    def __init__(self) -> None:
        self._estados: dict[str, BaseState] = {}
        self._actual: BaseState | None = None

    def registrar(self, nombre: str, estado: BaseState) -> None:
        self._estados[nombre] = estado

    def cambiar(self, nombre: str) -> None:
        self._actual = self._estados[nombre]

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._actual:
            self._actual.handle_event(event)

    def update(self, dt: float) -> None:
        if self._actual:
            self._actual.update(dt)

    def draw(self, pantalla: pygame.Surface) -> None:
        if self._actual:
            self._actual.draw(pantalla)
