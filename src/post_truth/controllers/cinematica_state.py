"""Pantalla de cinematicas (L3): reproduce un guion de data/cinematicas.json sobre el mapa. Enter avanza el dialogo,
ESC salta la escena entera. Al terminar va a `destino` (y llama a `al_terminar`, si se dio)."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models.cinematica import Interprete, contexto, guiones
from post_truth.views import sonido
from post_truth.views.cinematica_view import dibujar_cinematica


class CinematicaState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.ids, self.destino, self.al_terminar = [], "menu", None
        self.interprete: Interprete | None = None

    def reproducir(self, ids: str | list[str], destino: str, al_terminar=None) -> None:
        """Una o varias cinematicas seguidas (la revelacion y el final van juntas)."""
        self.ids, self.destino, self.al_terminar = [ids] if isinstance(ids, str) else list(ids), destino, al_terminar
        self.app.estados.cambiar("cinematica", fundido=True)

    def si_toca(self, destino: str) -> bool:
        """Si la partida tiene una cinematica pendiente (L4), la reproduce y despues vuelve a `destino`."""
        s = self.app.partida
        ids = s.cinematica_pendiente() if s is not None else []
        if ids:
            self.reproducir(ids, destino, s.terminar_apertura)
        return bool(ids)

    @property
    def mundo(self):
        return self.app.estados.estado("mundo")

    def al_entrar(self) -> None:
        self.terminada = False
        if self.app.partida is not None:   # las calles cerradas se ven como barreras
            self.mundo.mundo.sincronizar(self.app.partida.mapa)
        guion = [c for id in self.ids for c in guiones()[id]]
        self.interprete = Interprete(guion, contexto(self.app.partida), self.mundo.mundo.jugador,
                                     getattr(self.app, "avance_manual", False))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.interprete is None:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e, pygame.K_KP_ENTER):
            self.interprete.avanzar()
        elif event.key == pygame.K_ESCAPE:
            self.interprete.saltar()

    def update(self, dt: float) -> None:
        i = self.interprete
        i.update(dt)
        for nombre in i.sonidos:
            sonido.tocar(nombre)
        i.sonidos.clear()
        if i.terminado and not self.terminada:
            self.terminada = True
            if self.al_terminar is not None:
                self.al_terminar()
            self.app.estados.cambiar(self.destino, fundido=True)

    def datos_hud(self):
        return None   # en la escena no hay HUD: franjas negras

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_cinematica(pantalla, self.app.fuentes, self.app.temas.actual, self.mundo.mundo, self.interprete,
                           self.mundo.decorado)
