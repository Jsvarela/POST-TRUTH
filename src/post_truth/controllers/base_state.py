"""Interfaz que debe cumplir toda pantalla (patron State)."""
from abc import ABC, abstractmethod
import pygame


class BaseState(ABC):
    def __init__(self, app) -> None:
        self.app = app  # acceso al StateManager, temas y fuente compartidos

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """dt en segundos desde el ultimo frame (nunca time.sleep)."""

    @abstractmethod
    def draw(self, pantalla: pygame.Surface) -> None: ...
