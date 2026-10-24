"""Controlador de la seleccion: cada jugador elige un rol distinto y su personaje; la partida empieza cuando todos
tienen rol (los roles ya elegidos no se pueden repetir)."""
import pygame

from post_truth.config import ALTO, px
from post_truth.controllers.base_state import BaseState
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import MAX_JUGADORES
from post_truth.views.componentes import Boton, Panel
from post_truth.views.seleccion_view import dibujar_etiquetas, dibujar_seleccion

FASE_ROL, FASE_GENERO, FASE_LISTO = "rol", "genero", "listo"
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]


class SeleccionState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.fase = FASE_ROL
        self.rol: Role | None = None
        self.elegidos: list[Personaje] = []
        self.botones: list[Boton] = []
        self._construir()

    def al_entrar(self) -> None:
        self.fase, self.rol, self.elegidos = FASE_ROL, None, []
        self._construir()

    @property
    def tomados(self) -> dict[Role, int]:
        """Rol -> numero del jugador que ya lo eligio."""
        return {p.rol: i + 1 for i, p in enumerate(self.elegidos)}

    @property
    def puede_agregar(self) -> bool:
        return len(self.elegidos) < min(MAX_JUGADORES, len(Role))

    def _construir(self) -> None:
        if self.fase == FASE_ROL:
            tomados = self.tomados
            self.botones = []
            for i, rol in enumerate(Role):
                texto = f"{i + 1}. {rol.value}" + (f" (J{tomados[rol]})" if rol in tomados else "")
                b = Boton(pygame.Rect(px(60), px(140 + i * 88), px(340), px(64)), texto,
                          lambda r=rol: self._elegir_rol(r), atajo=ATAJOS[i])
                b.habilitado = rol not in tomados   # un rol por jugador
                self.botones.append(b)
        elif self.fase == FASE_GENERO:
            self.botones = [
                Boton(pygame.Rect(px(190), px(450), px(240), px(56)), "1. Hombre",
                      lambda: self._elegir_genero(Genero.HOMBRE), atajo=pygame.K_1),
                Boton(pygame.Rect(px(594), px(450), px(240), px(56)), "2. Mujer",
                      lambda: self._elegir_genero(Genero.MUJER), atajo=pygame.K_2),
                Boton(pygame.Rect(px(30), ALTO - px(84), px(160), px(50)), "Volver", self._volver),
            ]
        else:
            agregar = Boton(pygame.Rect(px(190), px(480), px(300), px(56)), "1. Agregar jugador",
                            self._agregar, atajo=pygame.K_1)
            agregar.habilitado = self.puede_agregar
            self.botones = [
                agregar,
                Boton(pygame.Rect(px(534), px(480), px(300), px(56)), "Enter: Iniciar partida", self._iniciar,
                      atajo=pygame.K_RETURN),
                Boton(pygame.Rect(px(30), ALTO - px(84), px(160), px(50)), "Volver", self._volver),
            ]

    def _elegir_rol(self, rol: Role) -> None:
        if rol in self.tomados:
            return
        self.rol, self.fase = rol, FASE_GENERO
        self._construir()

    def _elegir_genero(self, genero: Genero) -> None:
        assert self.rol is not None
        self.elegidos.append(Personaje(self.rol, genero))
        self.rol, self.fase = None, FASE_LISTO
        self._construir()

    def _agregar(self) -> None:
        if self.puede_agregar:
            self.fase = FASE_ROL
            self._construir()

    def _iniciar(self) -> None:
        if not self.elegidos or len(self.tomados) != len(self.elegidos):   # todos con un rol distinto
            return
        self.app.personajes = list(self.elegidos)
        self.app.personaje = self.elegidos[0]
        self.app.partida = None
        self.app.estados.cambiar(self.app.flujo)

    def _volver(self) -> None:
        if self.fase == FASE_GENERO:
            self.fase, self.rol = FASE_ROL, None
        elif self.fase == FASE_LISTO:            # se quita al ultimo jugador
            self.elegidos.pop()
            if not self.elegidos:
                self.fase = FASE_ROL
        elif self.elegidos:                      # cancela agregar otro jugador
            self.fase = FASE_LISTO
        else:
            self.app.estados.cambiar("menu")
            return
        self._construir()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._volver()
            return
        for boton in list(self.botones):
            if boton.handle_event(event):
                break

    def update(self, dt: float) -> None:
        pass

    def draw(self, pantalla: pygame.Surface) -> None:
        fuentes, tema = self.app.fuentes, self.app.temas.actual
        jugador = len(self.elegidos) + 1
        if self.fase == FASE_ROL:
            libres = [i for i, b in enumerate(self.botones) if b.habilitado]
            idx = next((i for i, b in enumerate(self.botones) if b.hover), libres[0] if libres else 0)
            rol = list(Role)[idx]
            panel = Panel(pygame.Rect(px(440), px(130), px(544), px(420)), rol.value)
            ejemplo = Personaje(rol, Genero.HOMBRE)
            dibujar_seleccion(
                pantalla, fuentes, tema, f"Jugador {jugador}: elige tu rol", "Cada jugador lleva un rol distinto",
                [panel], [(ejemplo, pygame.Rect(px(470), px(190), px(190), px(330)))],
                (pygame.Rect(px(680), px(190), px(280), px(300)), ejemplo.descripcion_rol),
                self.botones, "Clic o teclas 1-4 (los roles ya elegidos no estan disponibles)  |  ESC: volver")
        elif self.fase == FASE_GENERO:
            assert self.rol is not None
            paneles = [Panel(pygame.Rect(px(130), px(130), px(360), px(400))),
                       Panel(pygame.Rect(px(534), px(130), px(360), px(400)))]
            previas = [
                (Personaje(self.rol, Genero.HOMBRE), pygame.Rect(px(160), px(150), px(300), px(290))),
                (Personaje(self.rol, Genero.MUJER), pygame.Rect(px(564), px(150), px(300), px(290))),
            ]
            dibujar_seleccion(
                pantalla, fuentes, tema, f"Jugador {jugador}: elige tu personaje", f"Rol: {self.rol.value}",
                paneles, previas, None, self.botones, "Clic o teclas 1-2  |  ESC: volver")
        else:
            paneles, previas, etiquetas = [], [], []
            for i, p in enumerate(self.elegidos):
                caja = pygame.Rect(px(52) + i * px(230), px(120), px(220), px(340))
                paneles.append(Panel(caja, f"Jugador {i + 1}"))
                previas.append((p, pygame.Rect(caja.x + px(30), caja.y + px(56), px(160), px(240))))
                etiquetas.append((p.rol.value, (caja.centerx, caja.bottom - px(22))))
            dibujar_seleccion(
                pantalla, fuentes, tema, "Jugadores listos", "Todos tienen un rol distinto: ya pueden empezar",
                paneles, previas, None, self.botones, "1: agregar jugador  |  Enter: iniciar  |  ESC: quitar al ultimo")
            dibujar_etiquetas(pantalla, fuentes, tema, etiquetas)
