"""Controlador del mundo caminable (etapa M1: se prueba desde el menu con M).

Las teclas presionadas se guardan con KEYDOWN/KEYUP (no con pygame.key.get_pressed) para que el movimiento
se pueda probar sin ventana con eventos simulados. El movimiento ocurre en `update(dt)`.
"""
import pygame

from post_truth.config import RUTA_MUNDO
from post_truth.controllers.base_state import BaseState
from post_truth.models import Role
from post_truth.models.mundo import MundoCiudad
from post_truth.views.mundo_view import dibujar_mundo

# tecla -> (dx, dy)
DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 2.0   # segundos que se ve un aviso en la franja inferior


class MundoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
        self.presionadas: set[int] = set()
        self.aviso, self._t_aviso = "", 0.0

    def al_entrar(self) -> None:
        self.mundo = MundoCiudad.cargar(RUTA_MUNDO)   # cada visita empieza en el punto de aparicion
        self.presionadas.clear()
        self.aviso, self._t_aviso = "", 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.estados.cambiar("menu")
            elif event.key in DIRECCIONES:
                self.presionadas.add(event.key)
            elif event.key == pygame.K_e:
                zona = self.mundo.zona_al_alcance()
                if zona is not None:
                    # shortcut: en M1 solo se avisa; entrar a la pantalla de noticias del lugar es la etapa M2
                    self.aviso, self._t_aviso = f"{zona.capitalize()}: pronto podras entrar", DURACION_AVISO
        elif event.type == pygame.KEYUP:
            self.presionadas.discard(event.key)

    def update(self, dt: float) -> None:
        dx = sum(DIRECCIONES[k][0] for k in self.presionadas)
        dy = sum(DIRECCIONES[k][1] for k in self.presionadas)
        self.mundo.mover(dx, dy, dt)   # sin direccion (o teclas opuestas) no se mueve
        self._t_aviso = max(0.0, self._t_aviso - dt)
        if self._t_aviso == 0:
            self.aviso = ""

    def draw(self, pantalla: pygame.Surface) -> None:
        personaje = getattr(self.app, "personaje", None)
        color_rol = list(Role).index(personaje.rol) if personaje is not None else 0
        dibujar_mundo(pantalla, self.app.fuentes, self.app.temas.actual, self.mundo, color_rol, self.aviso)
