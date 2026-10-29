"""Controlador del mundo caminable: la calle entre noticia y noticia."""
import math
import random

import pygame

from post_truth.config import px, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_MAPA, RUTA_MINIJUEGOS
from post_truth.controllers import roles_teclas
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import load_trees
from post_truth.models import Role
from post_truth.models import minijuego as mj
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import FIN, FIN_DIA, PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.hud import DatosHud
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.decorado import generar as generar_decorado
from post_truth.views.mundo_view import RECT_MINIMAPA, Camara, EstadoMundo, dibujar_mundo
from post_truth.views.roles_view import dibujar_habilidad, dibujar_menu_aliados
from post_truth.views.telefono_view import dibujar_icono

DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 4.0
ALERTA_VIRAL = 3.0   # segundos que late el icono del telefono cuando algo se vuelve viral
RECT_TELEFONO = pygame.Rect(RECT_MINIMAPA.right - px(160), RECT_MINIMAPA.bottom + px(10), px(160), px(40))
RECT_HABILIDAD = pygame.Rect(RECT_MINIMAPA.right - px(220), RECT_TELEFONO.bottom + px(8), px(220), px(48))


def salud(c) -> float:
    """-1..1: lo bueno de la ciudad contra lo malo; 0 es la ciudad al empezar."""
    bueno = (c.verified_information + c.trust + c.coexistence + c.digital_wellbeing) / 4
    malo = (c.misinformation + c.conflicts) / 2
    return max(-1.0, min(1.0, (bueno - malo - 28.5) / 40))


class MundoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()
        self.mundo = MapaAbierto.cargar(RUTA_MAPA)
        self.presionadas: set[int] = set()
        self.aviso, self._t_aviso = "", 0.0
        self.guia = False
        self.animacion = AnimacionPersonaje()
        self.camara = Camara(self.mundo.jugador)
        self.decorado = generar_decorado(self.mundo)
        self.depuracion = False     # F3: zonas, colisiones y aristas
        self.t = 0.0
        self._dia = -1   # dia de campana que ya se preparo en el mundo
        self.anuncio: Anuncio | None = None   # grande, en el centro (el nuevo dia)
        self.toast: Anuncio | None = None     # corto, arriba
        self.alerta = 0.0
        self.menu_aliados = False   # Y: pedir ayuda a los aliados
        self.otros: dict[str, tuple[tuple[float, float], AnimacionPersonaje]] = {}   # multijugador: los demas

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
                getattr(self.app, "personajes", None) or [self.personaje], load_trees(RUTA_EVENTOS), GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng, extendido=self.app.tiempo_extendido,
                minijuegos=mj.cargar_lugares(RUTA_MINIJUEGOS))
            self._dia = -1
        if self.sesion.campana.dia != self._dia:   # amanece: de vuelta en la Plaza
            self._dia = self.sesion.campana.dia
            self.mundo.ir_a(self.sesion.mapa.zona_inicial)
            self._situar()
            self.guia = False
            self.animacion = AnimacionPersonaje()
            c = self.sesion.campana
            f = self.sesion.fase_actual
            texto = f"{f.nombre}: {f.descripcion}" if f else "Amanece en Ciudad Nova." 
            self.anuncio = Anuncio(f"Dia {c.dia + 1} de {len(c.dias)}", texto, "dia", duracion=2.4)
        self.mundo.sincronizar(self.sesion.mapa)   # el grafo manda: aristas que faltan = barreras
        self.camara.saltar(self.mundo.jugador)
        self.presionadas.clear()
        self.aviso, self._t_aviso = "", 0.0

    def _avisar(self, texto: str, titulo: str = "", tipo: str = "info") -> None:
        """El texto queda en la franja; con `titulo` ademas baja un toast animado."""
        self.aviso, self._t_aviso = texto, DURACION_AVISO
        if titulo:
            self.toast = Anuncio(titulo, texto, tipo, grande=False, duracion=DURACION_AVISO)

    def _situar(self) -> None:
        self.sesion.situar(self.jugador_id, self.mundo.jugador, self.zona_aqui())

    def zona_aqui(self) -> str | None:
        """La zona que pisa el jugador: E funciona en cualquier punto dentro de ella."""
        return self.mundo.zona_en(self.mundo.jugador)

    def accion_disponible(self) -> tuple[str, str] | None:
        """(zona, "entrar") si el jugador esta dentro de un lugar: E entra siempre y adentro se decide."""
        zona = self.zona_aqui()
        return (zona, "entrar") if zona is not None else None

    def etiqueta(self, que: str, zona: str) -> str:
        return f"Entrar a {self.mundo.zonas[zona].nombre}"

    def _usar(self) -> None:
        if self.zona_aqui() is not None:
            self.presionadas.clear()
            self.app.estados.cambiar("lugar", fundido=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            era, self.menu_aliados, aviso = roles_teclas.tecla(self.sesion, self.menu_aliados, event.key)
            if aviso is not None:
                self._avisar(aviso[1], aviso[0], aviso[2])
            if era:
                return
            if event.key == pygame.K_ESCAPE:
                self.app.salir_de_red()
                self.app.partida = None
                self.app.estados.cambiar("menu")
            elif event.key in DIRECCIONES:
                self.presionadas.add(event.key)
            elif event.key == pygame.K_e:
                self._usar()
            elif event.key == pygame.K_g:
                self.guia = not self.guia
            elif event.key == pygame.K_F3:
                self.depuracion = not self.depuracion
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
        self.mundo.sincronizar(self.sesion.mapa)   # una protesta puede cerrar una frontera a mitad del dia
        self._red(dt)
        antes, zona_antes = self.mundo.jugador, self.zona_aqui()
        self.mundo.mover(dx, dy, dt)
        zona = self.zona_aqui()
        if zona is not None and zona != zona_antes:
            self._avisar(f"Entraste a {self.mundo.zonas[zona].nombre}.")
        self._situar()
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
        if s.novedad == "mapa":                           # una protesta, una crisis de zona o un aislamiento
            s.novedad = ""
            n = s.notificaciones[-1]
            self._avisar(n["texto"], n["titulo"], n["tipo"])
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

    def _red(self, dt: float) -> None:
        """Multijugador: el servidor corrige una posicion invalida, y se anima a los demas entre fotos."""
        s = self.sesion
        if not getattr(s, "en_red", False):
            return
        if s.correccion is not None:
            self.mundo.jugador, s.correccion = s.correccion, None
            self._avisar("Por ahi no se puede pasar.", "No se puede pasar", "malo")
        if s.acciones and self.toast is None:
            titulo, texto, tipo = s.acciones.pop(0)   # lo que hicieron los demas (o un rechazo del servidor)
            self._avisar(texto, titulo, tipo)
        for jid, pos, direccion, caminando in s.remotos_en():
            antes, anim = self.otros.get(jid, (pos, AnimacionPersonaje()))
            anim.direccion = direccion
            anim.actualizar(0, 0, math.dist(antes, pos) if caminando else 0.0, dt)
            self.otros[jid] = (pos, anim)

    def vista_otros(self) -> tuple:
        s = self.sesion
        if not getattr(s, "en_red", False):
            return ()
        return tuple((s.nombre(jid) + ("" if s.conectados.get(jid, True) else " (sin conexion)"),
                      s.jugador(jid).personaje, pos, anim.nombre, anim.cuadro, s.conectados.get(jid, True))
                     for jid, (pos, anim) in self.otros.items())

    def estado_vista(self) -> EstadoMundo:
        s = self.sesion
        zonas, puntos = (self.mundo.ruta_puntos(s.mapa, self.mundo.ultima_zona, s.zona_noticia) if self.guia
                         else ((), []))
        inv = s.jugador_actual.investigacion
        return EstadoMundo(
            noticia=s.zona_noticia, evidencias=inv.lugares_pendientes() - {s.zona_noticia},
            accion=self.accion_disponible(),
            indicadores=s.ciudad.as_display_rows(), guia=zonas, guia_puntos=tuple(puntos), aviso=self.aviso,
            crisis=s.campana.crisis_lanzada and s.indice in s.campana.crisis, depuracion=self.depuracion,
            abiertas=frozenset(z.id for z in s.mapa.zonas()), zonas_crisis=frozenset(s.zonas_crisis),
            aisladas=frozenset(s.aisladas), noche=bool(s.fase_actual and s.fase_actual.variante == "noche"),
            salud=salud(s.ciudad),
            personaje=self.personaje, animacion=self.animacion, centro_camara=self.camara.centro,
            decorado=self.decorado, t=self.t,
            reloj=(s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None,
            dia=(s.campana.dia + 1, len(s.campana.dias)), fraccion_dia=s.campana.fraccion,
            credibilidad=s.jugador_actual.credibilidad, otros=self.vista_otros(),
            texto_accion=self.etiqueta(accion[1], accion[0]) if (accion := self.accion_disponible())
            and accion[1] != "elegir" else "")

    def datos_hud(self) -> DatosHud | None:
        s = self.sesion
        if s is None:
            return None
        f = s.fase_actual
        return DatosHud(s.ciudad.as_display_rows(), s.jugador_actual.credibilidad, "placa",
                        (s.campana.dia + 1, len(s.campana.dias)), f.nombre if f else "", s.campana.fraccion,
                        id(s.ciudad))

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        dibujar_mundo(pantalla, self.app.fuentes, tema, self.mundo, self.estado_vista())
        dibujar_icono(pantalla, self.app.fuentes, tema, RECT_TELEFONO, self.sesion.sin_leer, self.alerta, self.t)
        dibujar_habilidad(pantalla, self.app.fuentes, tema, RECT_HABILIDAD, roles_teclas.habilidad(self.sesion))
        if self.menu_aliados:
            dibujar_menu_aliados(pantalla, self.app.fuentes, tema, roles_teclas.filas_aliados(self.sesion))
        if self.app.estados.actual is not self:   # detras del telefono: sin anuncios encima
            return
        for a in (self.toast, self.anuncio):
            if a is not None:
                dibujar_anuncio(pantalla, self.app.fuentes, tema, a)
