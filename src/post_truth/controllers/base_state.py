"""Interfaz que debe cumplir toda pantalla."""
from abc import ABC, abstractmethod
import pygame


class BaseState(ABC):
    def __init__(self, app) -> None:
        self.app = app

    def al_entrar(self) -> None:
        """Se llama cada vez que este estado pasa a ser el activo."""

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """dt en segundos desde el ultimo frame."""

    @abstractmethod
    def draw(self, pantalla: pygame.Surface) -> None: ...
