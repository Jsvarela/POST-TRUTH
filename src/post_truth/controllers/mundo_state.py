"""Controlador del mundo caminable: la calle entre noticia y noticia.

Flujo (etapa M2): Menu -> Intro -> Seleccion -> MUNDO. La partida (PartidaSesion) vive en `app.partida` y es la
fuente de verdad: este estado la crea al empezar una partida nueva y la conserva al volver del interior de un
lugar. Llegar a una plaza actualiza la zona de la sesion (`llegar`), asi que la zona del mundo y la de la partida
siempre coinciden.

Con E, junto a la puerta de un lugar: si ahi ocurre la noticia activa se entra (EscenaState como interior); si
el lugar guarda evidencia de esa noticia, se busca. G muestra u oculta la guia.

Las teclas presionadas se guardan con KEYDOWN/KEYUP (no con pygame.key.get_pressed) para poder probar el
movimiento sin ventana con eventos simulados.
"""
import math
import random

import pygame

from post_truth.config import EVENTOS_POR_PARTIDA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_MUNDO
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import load_trees
from post_truth.models import Role
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.mundo import MundoCiudad
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.decorado import generar as generar_decorado
from post_truth.views.mundo_view import Camara, EstadoMundo, dibujar_mundo

# tecla -> (dx, dy)
DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 4.0   # segundos que se ve un aviso en la franja inferior


class MundoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()   # inyectable en pruebas para fijar las noticias de la partida
        self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
        self.presionadas: set[int] = set()
        self.aviso, self._t_aviso = "", 0.0
        self.guia = False
        self.animacion = AnimacionPersonaje()
        self.camara = Camara(self.mundo.jugador)
        self.decorado = generar_decorado(self.mundo)   # mismo mapa siempre: se genera una vez
        self.t = 0.0                                   # reloj del ambiente (viento, luces, pajaros)

    # --- partida ------------------------------------------------------------------------
    @property
    def personaje(self) -> Personaje:
        return getattr(self.app, "personaje", None) or Personaje(Role.CITIZEN, Genero.MUJER)

    @property
    def sesion(self) -> PartidaSesion:
        return self.app.partida

    @property
    def jugador_id(self) -> str:
        return self.sesion.jugador_actual.id

    def al_entrar(self) -> None:
        if self.app.partida is None:   # partida nueva: noticias sorteadas y el jugador en el punto de aparicion
            todos = load_trees(RUTA_EVENTOS)
            arboles = self.rng.sample(todos, min(EVENTOS_POR_PARTIDA, len(todos)))
            self.app.partida = PartidaSesion.nueva([self.personaje], arboles, GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                                                   GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng)
            self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
            self.sesion.llegar(self.jugador_id, self.mundo.ultima_plaza)
            self.guia = False
            self.animacion = AnimacionPersonaje()
        self.camara.saltar(self.mundo.jugador)
        self.presionadas.clear()       # al volver de un lugar no queda ninguna tecla "pegada"
        self.aviso, self._t_aviso = "", 0.0

    def _avisar(self, texto: str) -> None:
        self.aviso, self._t_aviso = texto, DURACION_AVISO

    def _llegar(self, zona: str) -> None:
        self.sesion.llegar(self.jugador_id, zona)

    # --- acciones -----------------------------------------------------------------------
    def accion_disponible(self) -> tuple[str, str] | None:
        """(zona, "entrar" | "evidencia") de lo que se puede hacer con E aqui, o None."""
        zona = self.mundo.zona_al_alcance()
        if zona is None:
            return None
        if zona == self.sesion.zona_noticia:
            return zona, "entrar"
        inv = self.sesion.jugador_actual.investigacion
        evidencia = inv.evidencia_en(zona)
        if evidencia is not None and not inv.esta_descubierta(evidencia.id):
            return zona, "evidencia"
        return None

    def _usar(self) -> None:
        accion = self.accion_disponible()
        if accion is None:
            zona = self.mundo.zona_al_alcance()
            if zona is not None:
                self._avisar(f"{zona.capitalize()}: aqui no hay nada de esta noticia.")
            return
        zona, que = accion
        if que == "entrar":
            self.sesion.buscar_evidencia(self.jugador_id)   # si el lugar de la noticia guarda evidencia, se ve adentro
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)   # entrar al lugar con un fundido corto
            return
        evidencia = self.sesion.buscar_evidencia(self.jugador_id)
        if evidencia is not None:
            self._avisar(f"{evidencia.titulo}: {evidencia.hallazgo}")

    # --- ciclo del estado -----------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.partida = None          # abandonar la partida
                self.app.estados.cambiar("menu")
            elif event.key in DIRECCIONES:
                self.presionadas.add(event.key)
            elif event.key == pygame.K_e:
                self._usar()
            elif event.key == pygame.K_g:
                self.guia = not self.guia
        elif event.type == pygame.KEYUP:
            self.presionadas.discard(event.key)

    def update(self, dt: float) -> None:
        dx = sum(DIRECCIONES[k][0] for k in self.presionadas)
        dy = sum(DIRECCIONES[k][1] for k in self.presionadas)
        antes = self.mundo.jugador
        self.mundo.mover(dx, dy, dt, self._llegar)   # sin direccion no se mueve
        self.animacion.actualizar(dx, dy, math.dist(antes, self.mundo.jugador), dt)
        self.camara.seguir(self.mundo.jugador, dt)
        self.t += dt
        self._t_aviso = max(0.0, self._t_aviso - dt)
        if self._t_aviso == 0:
            self.aviso = ""

    def estado_vista(self) -> EstadoMundo:
        s = self.sesion
        ruta = s.mapa.ruta(self.mundo.ultima_plaza, s.zona_noticia) if self.guia else None
        inv = s.jugador_actual.investigacion
        return EstadoMundo(
            noticia=s.zona_noticia, evidencias=inv.lugares_pendientes() - {s.zona_noticia},
            accion=self.accion_disponible(),
            indicadores=s.ciudad.as_display_rows(), guia=ruta.zonas if ruta else (), aviso=self.aviso,
            personaje=self.personaje, animacion=self.animacion, centro_camara=self.camara.centro,
            decorado=self.decorado, t=self.t)

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_mundo(pantalla, self.app.fuentes, self.app.temas.actual, self.mundo, self.estado_vista())
