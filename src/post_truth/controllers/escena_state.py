"""Controlador de la escena de dialogo."""
import random

import pygame

from post_truth.config import ANCHO, EVENTOS_POR_PARTIDA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, px
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.models.pistas import Investigacion, Pista
from post_truth.sesion import CONSECUENCIA, DECIDIENDO, FIN, TIEMPO_VIRAL, PartidaSesion, ResultadoDecision
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.componentes import Boton, CajaDialogo
from post_truth.views.escena_view import (AYUDA, AYUDA_INTERIOR, RECT_MAPA, RECT_TARJETA, EstadoPresentes,
                                          dibujar_escena)
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, zona_de_tecla, zona_en
from post_truth.views.tarjeta_civitas_view import EstadoTarjeta, pista_con_tecla, zona_en as zona_de_tarjeta

PROPAGACION = "propagacion"
RECT_DIALOGO = pygame.Rect(px(24), px(404), ANCHO - 2 * px(24), px(132))
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
Y_BOTONES, ALTO_BOTONES, MARGEN, SEPARACION = px(546), px(62), px(24), px(14)
TECLAS_INVESTIGAR = {pygame.K_a: "A", pygame.K_s: "S", pygame.K_d: "D", pygame.K_f: "F", pygame.K_g: "G"}
TECLAS_VIAJAR = {pygame.K_q: "Q", pygame.K_w: "W", pygame.K_e: "E", pygame.K_r: "R", pygame.K_t: "T"}


RECT_BOTON_CENTRAL = pygame.Rect((ANCHO - px(300)) // 2, Y_BOTONES, px(300), ALTO_BOTONES)


def _rects_botones(n: int) -> list[pygame.Rect]:
    """Reparte `n` botones a lo ancho de la pantalla."""
    ancho = (RECT_DIALOGO.width - SEPARACION * (n - 1)) // n
    return [pygame.Rect(MARGEN + i * (ancho + SEPARACION), Y_BOTONES, ancho, ALTO_BOTONES) for i in range(n)]


def _signo(impacto) -> int:
    """1 si la decision fue buena, -1 si fue mala, 0 si no cambio nada: manda el puntaje y, si es 0, el saldo de
    los indicadores (los malos restan)."""
    total = impacto.score or (impacto.verified_information + impacto.trust + impacto.coexistence
                              + impacto.digital_wellbeing - impacto.misinformation - impacto.conflicts)
    return (total > 0) - (total < 0)


class EscenaState(BaseState):
    """Traduce eventos de pygame a llamadas de `PartidaSesion`."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._rng = random.Random()
        self.eventos_por_partida: int | None = EVENTOS_POR_PARTIDA
        self._sesion: PartidaSesion | None = None
        self.dialogo = CajaDialogo(RECT_DIALOGO)
        self.botones: list[Boton] = []
        self.impacto = None
        self.animo = 0
        self.animacion: AnimacionPropagacion | None = None
        self._narracion = ""
        self.ruta_vista: tuple[str, ...] = ()
        self._hover = None
        self._hover_zona = None
        self.interior = False
        self._t = 0.0                  # reloj de la escena (respiracion de los presentes)
        self._reaccion: tuple[int, frozenset[str]] | None = None   # signo del impacto y a quienes les llego
        self._t_reaccion = 0.0

    @property
    def sesion(self) -> PartidaSesion:
        if self._sesion is None:
            self._sesion = self._crear_sesion(load_trees(RUTA_EVENTOS), random.Random(0))
        return self._sesion

    def _crear_sesion(self, arboles: list[DecisionTree], rng: random.Random) -> PartidaSesion:
        return PartidaSesion.nueva([self.personaje], arboles, GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                                   GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), rng)

    @property
    def rng(self) -> random.Random:
        return self._rng

    @rng.setter
    def rng(self, valor: random.Random) -> None:
        self._rng = valor
        if self._sesion is not None:
            self._sesion.rng = valor

    @property
    def personaje(self) -> Personaje:
        return getattr(self.app, "personaje", None) or Personaje(Role.CITIZEN, Genero.MUJER)

    @property
    def ciudad(self) -> CityState:
        return self.sesion.ciudad

    @property
    def grafo(self) -> GrafoSocial:
        return self.sesion.grafo

    @property
    def mapa(self) -> GrafoCiudad:
        return self.sesion.mapa

    @property
    def arboles(self) -> list[DecisionTree]:
        return self.sesion.arboles

    @property
    def arbol(self) -> DecisionTree:
        return self.sesion.arbol

    @property
    def indice(self) -> int:
        return self.sesion.indice

    @indice.setter
    def indice(self, valor: int) -> None:
        self.sesion.indice = valor

    @property
    def zona(self) -> str:
        return self.sesion.jugador_actual.zona

    @zona.setter
    def zona(self, valor: str) -> None:
        self.sesion.jugador_actual.zona = valor

    @property
    def investigacion(self) -> Investigacion:
        return self.sesion.jugador_actual.investigacion

    @property
    def fase(self) -> str:
        s = self.sesion
        if s.fase == DECIDIENDO and s.pendiente is not None:
            return PROPAGACION
        return s.fase

    def al_entrar(self) -> None:
        self.interior = self.app.partida is not None
        if self.interior:
            self._sesion = self.app.partida
            self.animacion = None
            if self._sesion.pendiente is not None:   # el reloj vencio en la calle: se muestra lo que paso
                self._mostrar_decision(self._sesion.pendiente)
                return
            self._preparar_turno()
            return
        todos = load_trees(RUTA_EVENTOS)
        arboles = self.rng.sample(todos, min(self.eventos_por_partida or len(todos), len(todos)))
        self._sesion = self._crear_sesion(arboles, self.rng)
        self.animacion = None
        self._preparar_turno()

    def _presentes(self) -> EstadoPresentes:
        """Los ciudadanos del lugar, con la apariencia de su rol; el genero sale del nombre y el tono, de su id."""
        personas = []
        alcanzados = self._reaccion[1] if self._reaccion else frozenset()
        for c in self.sesion.presentes:
            genero = Genero.MUJER if c.nombre.split()[0].endswith("a") else Genero.HOMBRE
            personas.append((c.nombre, Personaje(c.rol, genero, sum(map(ord, c.id)) % 2), c.id in alcanzados))
        return EstadoPresentes(personas, self._reaccion[0] if self._reaccion else None, self._t, self._t_reaccion)

    def _nombre_zona(self, id: str) -> str:
        return self.mapa.zona(id).nombre if id in self.mapa else id

    def _estado_mapa(self) -> EstadoMapa:
        decidiendo = self.fase == DECIDIENDO
        ruta = self.ruta_vista
        if decidiendo and self._hover_zona not in (None, self.zona):
            previa = self.mapa.ruta(self.zona, self._hover_zona)
            if previa is not None:
                ruta = previa.zonas
        return EstadoMapa(
            self.mapa, self.zona, ruta=ruta,
            pendientes=self.investigacion.lugares_pendientes() if decidiendo else set(),
            revisadas=self.investigacion.lugares_revisados(),
            hover=self._hover_zona if decidiendo else None, teclas=decidiendo,
            mostrar_ayuda=decidiendo and not self.interior)

    def _viajar(self, destino: str) -> None:
        """Ir a una zona cualquiera."""
        r = self.sesion.viajar(self.sesion.jugador_actual.id, destino)
        nombre = self._nombre_zona(destino)
        if not r.ok:
            if r.motivo == "sin_camino":
                self._decir_en_sitio(f"No hay camino hasta {nombre}.")
            return
        self.ruta_vista = r.ruta
        camino = " > ".join(self._nombre_zona(z) for z in r.ruta)
        aviso = f"Viajas a {nombre} por {camino}."
        if r.evidencia is not None:
            aviso += f" {r.evidencia.titulo}: {r.evidencia.hallazgo}"
        elif r.revisada:
            aviso += " Ya habias revisado lo de este lugar."
        else:
            aviso += " Aqui no hay nada de esta noticia."
        self._decir_en_sitio(aviso)

    def _manejar_mapa(self, event: pygame.event.Event) -> None:
        """Viajar: clic sobre una zona del mapa o su letra."""
        if self.interior:
            return
        if event.type == pygame.MOUSEMOTION:
            self._hover_zona = zona_en(self._estado_mapa(), RECT_MAPA, event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zona = zona_en(self._estado_mapa(), RECT_MAPA, event.pos)
            if zona is not None:
                self._viajar(zona)
        elif event.type == pygame.KEYDOWN and event.key in TECLAS_VIAJAR:
            zona = zona_de_tecla(self.mapa, TECLAS_VIAJAR[event.key])
            if zona is not None:
                self._viajar(zona)

    def _cargar_evento(self) -> None:
        """Abre la publicacion actual y prepara la pantalla."""
        self.sesion.abrir_evento()
        self._preparar_turno()

    def _preparar_turno(self) -> None:
        """Pantalla del jugador de turno: la noticia y sus botones."""
        self.impacto, self.animo = None, 0
        self._reaccion = None
        self._hover = self._hover_zona = None
        self.ruta_vista = ()
        self.dialogo.set_texto(self.arbol.event.content, "Civitas")
        self.sesion.iniciar_reloj()   # si es viral, desde aqui corre su tiempo
        evidencia = self.investigacion.evidencia_en(self.zona)
        if evidencia is not None and self.investigacion.esta_descubierta(evidencia.id):
            self._decir_en_sitio(f"Ya estas en {self._nombre_zona(self.zona)}. "
                                 f"{evidencia.titulo}: {evidencia.hallazgo}")
        self._construir_botones()

    def _construir_botones(self) -> None:
        """Un boton por rama del evento."""
        ramas = self.arbol.root.children[:4]
        self.botones = [Boton(rect, f"{i + 1}. {nodo.label}", lambda n=nodo: self._decidir(n), atajo=ATAJOS[i])
                        for i, (rect, nodo) in enumerate(zip(_rects_botones(len(ramas)), ramas))]

    def _decir_en_sitio(self, aviso: str) -> None:
        """Muestra la noticia y debajo el aviso, sin volver a animar el texto."""
        self.dialogo.set_texto(f"{self.arbol.event.content}\n{aviso}", "Civitas")
        self.dialogo.completar()

    def _investigar(self, pista: Pista) -> None:
        """Revisa una pista de la tarjeta: revela el hallazgo y marca la zona."""
        r = self.sesion.investigar(self.sesion.jugador_actual.id, pista)
        if r.ok:
            self._decir_en_sitio(f"{pista.titulo}: {pista.hallazgo}")

    def _decidir(self, nodo: DecisionNode) -> None:
        r = self.sesion.decidir(self.sesion.jugador_actual.id, nodo)
        if r.ok:
            self._mostrar_decision(r)

    def _mostrar_decision(self, r: ResultadoDecision) -> None:
        if r.simulacion is None:
            self._cerrar_decision(r)
            return
        self.animacion = AnimacionPropagacion(self.grafo, r.simulacion)
        self.animo = 0
        self._narracion = self.animacion.narracion()
        self.dialogo.set_texto(self._narracion, "Civitas")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Saltar animacion (Enter)",
                              self.animacion.saltar, atajo=pygame.K_RETURN)]

    def _cerrar_decision(self, r: ResultadoDecision) -> None:
        """La sesion aplica el impacto a la ciudad y a los puntos."""
        self.sesion.aplicar()
        self.impacto = r.impacto
        self.animo = _signo(r.impacto)
        olas = r.simulacion.resultado.olas[1:] if r.simulacion is not None else ()
        self._reaccion = (self.animo, frozenset(id for ola in olas for id in ola))   # quienes la recibieron
        self._t_reaccion = 0.0
        mensaje = r.nodo.consecuencia(self.investigacion.pistas_descubiertas()) or "Nada cambia por ahora."
        self.dialogo.set_texto(f"{mensaje}\n{r.aviso}" if r.aviso else mensaje, "Consecuencia")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Continuar (Enter)",
                              self._continuar, atajo=pygame.K_RETURN)]

    def _terminar_propagacion(self) -> None:
        """Pasa de la animacion a las consecuencias: efecto del arbol + efecto de la propagacion."""
        assert self.animacion is not None and self.sesion.pendiente is not None
        self.animacion = None
        self._cerrar_decision(self.sesion.pendiente)

    def _continuar(self) -> None:
        self.sesion.continuar()
        if self.sesion.fase != FIN:
            if self.interior:
                self.app.estados.cambiar("mundo", fundido=True)
                return
            self._preparar_turno()
            return
        self.impacto, self.animo = None, 1 if self.ciudad.score >= 0 else -1
        self.dialogo.set_texto(f"Termino la jornada en Ciudad Nova. Tu puntaje final es {self.ciudad.score}.", "Fin")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Volver al menu (Enter)", self._volver_al_menu,
                              atajo=pygame.K_RETURN)]

    def _volver_al_menu(self) -> None:
        self.app.partida = None
        self.app.estados.cambiar("menu")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if not self.interior:
                self.app.estados.cambiar("menu")
            elif self.fase == DECIDIENDO:
                self.app.estados.cambiar("mundo", fundido=True)
            elif self.fase == FIN:
                self._volver_al_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.dialogo.completar()
        if event.type == pygame.MOUSEBUTTONDOWN and RECT_DIALOGO.collidepoint(event.pos):
            self.dialogo.completar()
        if self.fase == DECIDIENDO:
            self._manejar_mapa(event)
            self._manejar_investigacion(event)
        for boton in list(self.botones):
            if boton.handle_event(event):
                break

    def _manejar_investigacion(self, event: pygame.event.Event) -> None:
        """Investigar: clic sobre una zona de la tarjeta con pista, o su letra."""
        evento = self.arbol.event
        if event.type == pygame.MOUSEMOTION:
            self._hover = zona_de_tarjeta(RECT_TARJETA, event.pos, evento)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zona = zona_de_tarjeta(RECT_TARJETA, event.pos, evento)
            pista = self.investigacion.pista_en(zona) if zona is not None else None
            if pista is not None:
                self._investigar(pista)
        elif event.type == pygame.KEYDOWN and event.key in TECLAS_INVESTIGAR:
            pista = pista_con_tecla(evento, TECLAS_INVESTIGAR[event.key])
            if pista is not None:
                self._investigar(pista)

    def update(self, dt: float) -> None:
        self.dialogo.update(dt)
        self._t += dt
        self._t_reaccion += dt
        if self.fase == DECIDIENDO:
            vencida = self.sesion.transcurrir(dt)
            if vencida is not None:
                self._mostrar_decision(vencida)
        if self.fase == PROPAGACION and self.animacion is not None:
            self.animacion.update(dt)
            narracion = self.animacion.narracion()
            if narracion != self._narracion:
                self._narracion = narracion
                self.dialogo.set_texto(narracion, "Civitas")
            if self.animacion.terminada and self.botones[0].texto.startswith("Saltar"):
                self.botones = [Boton(RECT_BOTON_CENTRAL, "Ver consecuencias (Enter)",
                                      self._terminar_propagacion, atajo=pygame.K_RETURN)]

    def draw(self, pantalla: pygame.Surface) -> None:
        if self.fase == FIN:
            titulo, texto = "Fin de la jornada", "Gracias por cuidar Ciudad Nova."
        elif self.fase == CONSECUENCIA:
            titulo, texto = "Consecuencias", ""
        else:
            titulo, texto = "", ""
        en_mapa = self.fase in (DECIDIENDO, CONSECUENCIA)
        dibujar_escena(pantalla, self.app.fuentes, self.app.temas.actual, self.personaje, self.animo,
                       self.ciudad.as_display_rows(), titulo, texto, self.impacto, self.dialogo, self.botones,
                       self.animacion if self.fase == PROPAGACION else None, self.zona,
                       self._nombre_zona(self.zona) if self.zona else "",
                       self._estado_mapa() if en_mapa else None,
                       EstadoTarjeta(self.arbol.event, self.investigacion, self._hover)
                       if self.fase == DECIDIENDO else None, AYUDA_INTERIOR if self.interior else AYUDA,
                       self._reloj() if self.fase == DECIDIENDO else None,
                       self._presentes() if self.interior and self.fase in (DECIDIENDO, CONSECUENCIA) else None,
                       (self._reaccion[0], self._t_reaccion) if self._reaccion and self.fase == CONSECUENCIA else None)

    def _reloj(self) -> tuple[float, float] | None:
        restante = self.sesion.tiempo_restante
        return None if restante is None else (restante, TIEMPO_VIRAL)
