"""Controlador del mundo caminable: la calle entre noticia y noticia."""
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
from post_truth.sesion import TIEMPO_VIRAL, PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.decorado import generar as generar_decorado
from post_truth.views.mundo_view import Camara, EstadoMundo, dibujar_mundo

DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 4.0


def mapa_de_tiempos(mapa: GrafoCiudad, mundo: MundoCiudad) -> GrafoCiudad:
    """El mismo grafo de la ciudad, pero cada arista pesa lo que se tarda caminandola en el mundo."""
    datos = mapa.to_dict()
    tiempos = {frozenset((c.desde, c.hasta)): mundo.tiempo_calle(c) for c in mundo.calles}
    for c in datos["conexiones"]:
        c["distancia"] = max(1, round(100 * tiempos[frozenset((c["origen"], c["destino"]))]))
    return GrafoCiudad.from_dict(datos)


class MundoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()
        self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
        self.presionadas: set[int] = set()
        self.aviso, self._t_aviso = "", 0.0
        self.guia = False
        self.animacion = AnimacionPersonaje()
        self.camara = Camara(self.mundo.jugador)
        self.decorado = generar_decorado(self.mundo)
        self.mapa_guia = mapa_de_tiempos(GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.mundo)
        self.t = 0.0

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
        if self.app.partida is None:
            todos = load_trees(RUTA_EVENTOS)
            arboles = self.rng.sample(todos, min(EVENTOS_POR_PARTIDA, len(todos)))
            self.app.partida = PartidaSesion.nueva([self.personaje], arboles, GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                                                   GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng)
            self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
            self.sesion.llegar(self.jugador_id, self.mundo.ultima_plaza)
            self.guia = False
            self.animacion = AnimacionPersonaje()
        self.camara.saltar(self.mundo.jugador)
        self.presionadas.clear()
        self.aviso, self._t_aviso = "", 0.0

    def _avisar(self, texto: str) -> None:
        self.aviso, self._t_aviso = texto, DURACION_AVISO

    def _llegar(self, zona: str) -> None:
        self.sesion.llegar(self.jugador_id, zona)

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
            self.sesion.buscar_evidencia(self.jugador_id)
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)
            return
        evidencia = self.sesion.buscar_evidencia(self.jugador_id)
        if evidencia is not None:
            self._avisar(f"{evidencia.titulo}: {evidencia.hallazgo}")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.partida = None
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
        self.mundo.mover(dx, dy, dt, self._llegar)
        self.animacion.actualizar(dx, dy, math.dist(antes, self.mundo.jugador), dt)
        self.camara.seguir(self.mundo.jugador, dt)
        self.t += dt
        if self.sesion.transcurrir(dt) is not None:      # vencio buscando evidencia: se ve adentro lo que paso
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)
        self._t_aviso = max(0.0, self._t_aviso - dt)
        if self._t_aviso == 0:
            self.aviso = ""

    def estado_vista(self) -> EstadoMundo:
        s = self.sesion
        ruta = self.mapa_guia.ruta(self.mundo.ultima_plaza, s.zona_noticia) if self.guia else None
        inv = s.jugador_actual.investigacion
        return EstadoMundo(
            noticia=s.zona_noticia, evidencias=inv.lugares_pendientes() - {s.zona_noticia},
            accion=self.accion_disponible(),
            indicadores=s.ciudad.as_display_rows(), guia=ruta.zonas if ruta else (), aviso=self.aviso,
            personaje=self.personaje, animacion=self.animacion, centro_camara=self.camara.centro,
            decorado=self.decorado, t=self.t,
            reloj=(s.tiempo_restante, TIEMPO_VIRAL) if s.reloj_activo else None)

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_mundo(pantalla, self.app.fuentes, self.app.temas.actual, self.mundo, self.estado_vista())
