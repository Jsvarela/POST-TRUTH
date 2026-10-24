"""Controlador del mundo caminable: la calle entre noticia y noticia."""
import math
import random

import pygame

from post_truth.config import px, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_MINIJUEGOS, RUTA_MUNDO
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import load_trees
from post_truth.models import Role
from post_truth.models import minijuego as mj
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.mundo import MundoCiudad
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import FIN, FIN_DIA, PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.decorado import generar as generar_decorado
from post_truth.views.mundo_view import RECT_MINIMAPA, Camara, EstadoMundo, dibujar_mundo
from post_truth.views.telefono_view import dibujar_icono

DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 4.0
ALERTA_VIRAL = 3.0   # segundos que late el icono del telefono cuando algo se vuelve viral
RECT_TELEFONO = pygame.Rect(RECT_MINIMAPA.right - px(160), RECT_MINIMAPA.bottom + px(10), px(160), px(40))


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
        self._dia = -1   # dia de campana que ya se preparo en el mundo
        self.anuncio: Anuncio | None = None   # grande, en el centro (el nuevo dia)
        self.toast: Anuncio | None = None     # corto, arriba
        self.alerta = 0.0

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
            self.app.partida = PartidaSesion.nueva_campana(
                [self.personaje], load_trees(RUTA_EVENTOS), GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng, extendido=self.app.tiempo_extendido,
                minijuegos=mj.cargar_lugares(RUTA_MINIJUEGOS))
            self._dia = -1
        if self.sesion.campana.dia != self._dia:   # amanece: de vuelta en la Plaza
            self._dia = self.sesion.campana.dia
            self.mundo = MundoCiudad.cargar(RUTA_MUNDO)
            self.sesion.llegar(self.jugador_id, self.mundo.ultima_plaza)
            self.guia = False
            self.animacion = AnimacionPersonaje()
            c = self.sesion.campana
            texto = ("Empieza la campana: frena los rumores antes de la eleccion." if c.dia == 0
                     else "Amanece en Ciudad Nova. Nuevas noticias circulan por la red.")
            self.anuncio = Anuncio(f"Dia {c.dia + 1} de {len(c.dias)}", texto, "dia", duracion=2.4)
        self.camara.saltar(self.mundo.jugador)
        self.presionadas.clear()
        self.aviso, self._t_aviso = "", 0.0
        self.menu: list[str] = []   # opciones del lugar cuando hay mas de una (E las muestra, 1-3 elige)

    def _avisar(self, texto: str, titulo: str = "", tipo: str = "info") -> None:
        """El texto queda en la franja; con `titulo` ademas baja un toast animado."""
        self.aviso, self._t_aviso = texto, DURACION_AVISO
        if titulo:
            self.toast = Anuncio(titulo, texto, tipo, grande=False, duracion=DURACION_AVISO)

    def _llegar(self, zona: str) -> None:
        self.sesion.llegar(self.jugador_id, zona)

    def opciones(self, zona: str) -> list[str]:
        """Lo que se puede hacer en `zona`: "entrar" (la noticia), "evidencia" y/o "minijuego"."""
        inv = self.sesion.jugador_actual.investigacion
        evidencia = inv.evidencia_en(zona)
        if zona == self.sesion.zona_noticia:
            ops = ["entrar"]
        elif evidencia is not None and not inv.esta_descubierta(evidencia.id):
            ops = ["evidencia"]
        else:
            ops = []
        return ops + (["minijuego"] if self.sesion.minijuego_en(zona) else [])

    def accion_disponible(self) -> tuple[str, str] | None:
        """(zona, "entrar" | "evidencia" | "minijuego" | "elegir") de lo que hace E aqui, o None."""
        zona = self.mundo.zona_al_alcance()
        ops = self.opciones(zona) if zona is not None else []
        if not ops:
            return None
        return zona, ops[0] if len(ops) == 1 else "elegir"

    def etiqueta(self, que: str, zona: str) -> str:
        if que == "entrar":
            return f"Entrar a la noticia de {zona.capitalize()}"
        if que == "evidencia":
            return f"Buscar evidencia en {zona.capitalize()}"
        return f"Jugar {mj.REGISTRO[self.sesion.minijuego_en(zona)].nombre}"

    def _usar(self) -> None:
        if self.menu:
            self.menu = []
            return
        accion = self.accion_disponible()
        if accion is None:
            zona = self.mundo.zona_al_alcance()
            if zona is not None:
                self._avisar(f"{zona.capitalize()}: aqui no hay nada de esta noticia.", "Nada por aqui")
            return
        zona, que = accion
        if que == "elegir":
            self.menu = self.opciones(zona)
            return
        self._hacer(zona, que)

    def _hacer(self, zona: str, que: str) -> None:
        self.menu = []
        if que == "minijuego":
            if self.sesion.iniciar_minijuego(zona) is not None:
                self.presionadas.clear()
                self.app.estados.cambiar("minijuego", fundido=True)
            return
        if que == "entrar":
            self.sesion.buscar_evidencia(self.jugador_id)
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)
            return
        evidencia = self.sesion.buscar_evidencia(self.jugador_id)
        if evidencia is not None:
            self._avisar(f"{evidencia.titulo}: {evidencia.hallazgo}", "Evidencia encontrada", "bueno")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.menu:
                self.menu = []
            elif event.key == pygame.K_ESCAPE:
                self.app.partida = None
                self.app.estados.cambiar("menu")
            elif self.menu and pygame.K_1 <= event.key < pygame.K_1 + len(self.menu):
                self._hacer(self.mundo.zona_al_alcance(), self.menu[event.key - pygame.K_1])
            elif event.key in DIRECCIONES:
                self.presionadas.add(event.key)
            elif event.key == pygame.K_e:
                self._usar()
            elif event.key == pygame.K_g:
                self.guia = not self.guia
            elif event.key == pygame.K_t:
                self.presionadas.clear()
                self.app.estados.cambiar("telefono")
        elif event.type == pygame.KEYUP:
            self.presionadas.discard(event.key)

    def update(self, dt: float) -> None:
        for anuncio in ("anuncio", "toast"):
            a = getattr(self, anuncio)
            if a is not None:
                a.avanzar(dt)
                if a.terminado:
                    setattr(self, anuncio, None)
        self.alerta = max(0.0, self.alerta - dt)
        dx = sum(DIRECCIONES[k][0] for k in self.presionadas)
        dy = sum(DIRECCIONES[k][1] for k in self.presionadas)
        antes = self.mundo.jugador
        self.mundo.mover(dx, dy, dt, self._llegar)
        if self.menu and self.accion_disponible() is None:   # se alejo del lugar
            self.menu = []
        self.animacion.actualizar(dx, dy, math.dist(antes, self.mundo.jugador), dt)
        self.camara.seguir(self.mundo.jugador, dt)
        self.t += dt
        s = self.sesion
        vencida = s.transcurrir(dt)
        if s.novedad == "viral":
            s.novedad = ""
            self.alerta = ALERTA_VIRAL
            sonido.alerta()
            self._avisar("El rumor ya llega a mucha gente: abre el telefono (T).", "Se volvio viral!", "malo")
        if s.novedad == "crisis":                         # la crisis abre el telefono (que la anuncia)
            self._avisar(f"Crisis viral en {s.zona_noticia.capitalize()}! Corre antes de que se riegue.")
            self.presionadas.clear()
            self.anuncio = None
            self.app.estados.cambiar("telefono")
        elif vencida is not None:                           # vencio buscando evidencia: se ve adentro lo que paso
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)
        elif s.fase in (FIN_DIA, FIN):                    # se acabo el dia en la calle
            self.presionadas.clear()
            self.app.estados.cambiar("resumen", fundido=True)
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
            reloj=(s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None,
            dia=(s.campana.dia + 1, len(s.campana.dias)), fraccion_dia=s.campana.fraccion,
            credibilidad=s.jugador_actual.credibilidad,
            menu=tuple(self.etiqueta(o, self.mundo.zona_al_alcance()) for o in self.menu),
            texto_accion=self.etiqueta(accion[1], accion[0]) if (accion := self.accion_disponible())
            and accion[1] != "elegir" else "")

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        dibujar_mundo(pantalla, self.app.fuentes, tema, self.mundo, self.estado_vista())
        dibujar_icono(pantalla, self.app.fuentes, tema, RECT_TELEFONO, self.sesion.sin_leer, self.alerta, self.t)
        if self.app.estados.actual is not self:   # detras del telefono: sin anuncios encima
            return
        for a in (self.toast, self.anuncio):
            if a is not None:
                dibujar_anuncio(pantalla, self.app.fuentes, tema, a)
