"""Controlador de la escena de dialogo (novela visual de decisiones).

Flujo por publicacion: DECIDIENDO (noticia + botones) -> [PROPAGACION] -> CONSECUENCIA
(mensaje + efecto en la ciudad) -> siguiente publicacion ... -> FIN. Todo el contenido sale
del DecisionTree cargado desde data/events.json; aqui no hay noticias fijas.

INVESTIGAR: cada publicacion es una tarjeta de Civitas con zonas clicables (autor, fuente,
fecha, imagen, texto, estadisticas) que esconden pistas, y ademas deja EVIDENCIA en lugares del mapa
de la ciudad (un testigo, un documento, una grabacion). Revisar y viajar son gratis.

El ESTADO y las REGLAS (ciudad, jugadores, zona, hallazgos, puntos, turnos, decidir/viajar/investigar)
viven en `sesion.PartidaSesion`, que no sabe de pygame y es serializable; este controlador solo traduce eventos
a llamadas de la sesion y maneja lo visual (dialogo, botones, hover y la animacion de la propagacion).

VIAJAR: el jugador puede ir a CUALQUIER zona (clic en el mapa o Q W E R T). El viaje cuesta la
distancia del camino mas corto (Dijkstra, ver structures/grafo_ciudad.py) y al llegar se revela la
evidencia de la noticia que haya alli. La posicion se mantiene entre publicaciones. Los rumores NO
se propagan por el mapa: eso ocurre solo en el grafo social, entre personas.

VERIFICAR Y REPORTAR no exigen estar en ningun lugar: su resultado depende del RESPALDO reunido
(Investigacion.respaldo: 0 nada, 1 solo tarjeta, 2 evidencia de campo). Ver structures/propagacion.py.

PROPAGACION solo ocurre si la decision mueve la publicacion por el grafo social (Compartir,
Verificar, Reportar con pruebas; Ignorar no). El efecto sobre los indicadores se aplica DESPUES de
la animacion, para que el jugador vea primero como viaja la noticia y luego sus consecuencias.
"""
import random

import pygame

from post_truth.config import ANCHO, EVENTOS_POR_PARTIDA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, px
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.models.pistas import Investigacion, Pista
from post_truth.sesion import CONSECUENCIA, DECIDIENDO, FIN, PartidaSesion, ResultadoDecision
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.componentes import Boton, CajaDialogo
from post_truth.views.escena_view import AYUDA, AYUDA_INTERIOR, RECT_MAPA, RECT_TARJETA, dibujar_escena
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, zona_de_tecla, zona_en
from post_truth.views.tarjeta_civitas_view import EstadoTarjeta, pista_con_tecla, zona_en as zona_de_tarjeta

PROPAGACION = "propagacion"   # solo existe en la pantalla: la sesion sigue "decidiendo" con una decision pendiente
RECT_DIALOGO = pygame.Rect(px(24), px(404), ANCHO - 2 * px(24), px(132))
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
Y_BOTONES, ALTO_BOTONES, MARGEN, SEPARACION = px(546), px(62), px(24), px(14)
# Teclas para investigar la 1.a, 2.a... pista de la tarjeta (letras de views/tarjeta_civitas_view.TECLAS_PISTA)
TECLAS_INVESTIGAR = {pygame.K_a: "A", pygame.K_s: "S", pygame.K_d: "D", pygame.K_f: "F", pygame.K_g: "G"}
# Teclas para viajar a la 1.a, 2.a... zona del mapa (letras de views/mapa_view.TECLAS_VIAJE)
TECLAS_VIAJAR = {pygame.K_q: "Q", pygame.K_w: "W", pygame.K_e: "E", pygame.K_r: "R", pygame.K_t: "T"}


# Boton unico (Continuar, Saltar, Ver consecuencias...): centrado bajo el dialogo
RECT_BOTON_CENTRAL = pygame.Rect((ANCHO - px(300)) // 2, Y_BOTONES, px(300), ALTO_BOTONES)


def _rects_botones(n: int) -> list[pygame.Rect]:
    """Reparte `n` botones a lo ancho de la pantalla (3 o 4 segun las ramas del evento)."""
    ancho = (RECT_DIALOGO.width - SEPARACION * (n - 1)) // n
    return [pygame.Rect(MARGEN + i * (ancho + SEPARACION), Y_BOTONES, ancho, ALTO_BOTONES) for i in range(n)]


class EscenaState(BaseState):
    """Controlador delgado: traduce eventos de pygame a llamadas de `PartidaSesion` (donde viven el estado y las
    reglas) y pide a la vista que dibuje. Aqui solo queda lo visual: dialogo, botones, hover y la animacion."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._rng = random.Random()  # inyectable en pruebas para fijar el orden
        self.eventos_por_partida: int | None = EVENTOS_POR_PARTIDA   # None = todas las publicaciones (pruebas)
        self._sesion: PartidaSesion | None = None
        self.dialogo = CajaDialogo(RECT_DIALOGO)
        self.botones: list[Boton] = []
        self.impacto = None                  # efecto ya escalado por rol, para mostrarlo
        self.animo = 0                       # reaccion del personaje: -1, 0, 1
        self.animacion: AnimacionPropagacion | None = None
        self._narracion = ""
        self.ruta_vista: tuple[str, ...] = ()   # ultima ruta recorrida en esta publicacion (se resalta en el mapa)
        self._hover = None        # zona de la tarjeta bajo el mouse
        self._hover_zona = None   # zona del mapa bajo el mouse
        # True si se entro desde el mundo caminable: la partida es la del mundo, no se viaja con el minimapa
        # (se camina) y al terminar cada noticia se vuelve a la calle
        self.interior = False

    # --- el estado vive en la sesion ----------------------------------------------------
    @property
    def sesion(self) -> PartidaSesion:
        if self._sesion is None:   # antes de entrar a la escena: una sesion de relleno, sin tocar el rng
            self._sesion = self._crear_sesion(load_trees(RUTA_EVENTOS), random.Random(0))
        return self._sesion

    def _crear_sesion(self, arboles: list[DecisionTree], rng: random.Random) -> PartidaSesion:
        # shortcut: un solo jugador; el multijugador pasara la lista de personajes aqui (ver PartidaSesion)
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
        # Respaldo para poder abrir la escena directamente (pruebas) sin pasar por la seleccion.
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
            return PROPAGACION     # la decision ya se calculo; falta ver como viaja la noticia
        return s.fase

    def al_entrar(self) -> None:
        self.interior = self.app.partida is not None
        if self.interior:                             # entrar a un lugar desde el mundo: misma partida
            self._sesion = self.app.partida
            self.animacion = None
            self._preparar_turno()
            return
        todos = load_trees(RUTA_EVENTOS)
        # Cada partida juega una seleccion al azar (y en orden al azar): el contenido cambia entre partidas
        arboles = self.rng.sample(todos, min(self.eventos_por_partida or len(todos), len(todos)))
        self._sesion = self._crear_sesion(arboles, self.rng)
        self.animacion = None
        self._preparar_turno()

    # --- mapa y viajes ------------------------------------------------------------------
    def _nombre_zona(self, id: str) -> str:
        return self.mapa.zona(id).nombre if id in self.mapa else id

    def _estado_mapa(self) -> EstadoMapa:
        decidiendo = self.fase == DECIDIENDO
        ruta = self.ruta_vista
        if decidiendo and self._hover_zona not in (None, self.zona):   # vista previa de la ruta bajo el mouse
            previa = self.mapa.ruta(self.zona, self._hover_zona)
            if previa is not None:
                ruta = previa.zonas
        return EstadoMapa(
            self.mapa, self.zona, ruta=ruta,
            pendientes=self.investigacion.lugares_pendientes() if decidiendo else set(),
            revisadas=self.investigacion.lugares_revisados(),
            hover=self._hover_zona if decidiendo else None, teclas=decidiendo,
            mostrar_ayuda=decidiendo and not self.interior)   # la franja de ayuda solo sirve mientras se decide

    def _viajar(self, destino: str) -> None:
        """Ir a una zona cualquiera (la sesion la mueve por el camino mas corto y revela la evidencia)."""
        r = self.sesion.viajar(self.sesion.jugador_actual.id, destino)
        nombre = self._nombre_zona(destino)
        if not r.ok:
            if r.motivo == "sin_camino":
                self._decir_en_sitio(f"No hay camino hasta {nombre}.")
            return    # fuera de turno, misma zona o zona desconocida: no pasa nada
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
        """Viajar: clic sobre una zona del mapa o su letra (Q W E R T); el mouse encima muestra la ruta.
        Dentro de un lugar del mundo no se viaja con el minimapa: se sale a la calle y se camina."""
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

    # --- transiciones -------------------------------------------------------------------
    def _cargar_evento(self) -> None:
        """Abre la publicacion actual y prepara la pantalla."""
        self.sesion.abrir_evento()
        self._preparar_turno()

    def _preparar_turno(self) -> None:
        """Pantalla del jugador de turno: la noticia y sus botones."""
        self.impacto, self.animo = None, 0
        self._hover = self._hover_zona = None
        self.ruta_vista = ()
        self.dialogo.set_texto(self.arbol.event.content, "Civitas")
        # Si el jugador ya esta parado donde la noticia dejo evidencia, la sesion la revelo sola
        evidencia = self.investigacion.evidencia_en(self.zona)
        if evidencia is not None and self.investigacion.esta_descubierta(evidencia.id):
            self._decir_en_sitio(f"Ya estas en {self._nombre_zona(self.zona)}. "
                                 f"{evidencia.titulo}: {evidencia.hallazgo}")
        self._construir_botones()

    def _construir_botones(self) -> None:
        """Un boton por rama del evento (las acciones cambian segun la noticia: "Verificar", "Buscar
        video completo", ...). Siempre estan todas disponibles: lo que cambia es cuanto rinden segun
        el respaldo reunido, no si se pueden elegir."""
        ramas = self.arbol.root.children[:4]
        self.botones = [Boton(rect, f"{i + 1}. {nodo.label}", lambda n=nodo: self._decidir(n), atajo=ATAJOS[i])
                        for i, (rect, nodo) in enumerate(zip(_rects_botones(len(ramas)), ramas))]

    def _decir_en_sitio(self, aviso: str) -> None:
        """Muestra la noticia y debajo el aviso, sin volver a animar el texto (ya se leyo)."""
        self.dialogo.set_texto(f"{self.arbol.event.content}\n{aviso}", "Civitas")
        self.dialogo.completar()

    def _investigar(self, pista: Pista) -> None:
        """Revisa una pista de la tarjeta: revela el hallazgo (o lo relee) y marca la zona."""
        r = self.sesion.investigar(self.sesion.jugador_actual.id, pista)
        if r.ok:
            self._decir_en_sitio(f"{pista.titulo}: {pista.hallazgo}")

    def _decidir(self, nodo: DecisionNode) -> None:
        r = self.sesion.decidir(self.sesion.jugador_actual.id, nodo)
        if not r.ok:
            return
        if r.simulacion is None:          # Ignorar, una respuesta sin tipo o un reporte rechazado: nada que animar
            self._cerrar_decision(r)
            return
        self.animacion = AnimacionPropagacion(self.grafo, r.simulacion)
        self.animo = 0
        self._narracion = self.animacion.narracion()
        self.dialogo.set_texto(self._narracion, "Civitas")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Saltar animacion (Enter)",
                              self.animacion.saltar, atajo=pygame.K_RETURN)]

    def _cerrar_decision(self, r: ResultadoDecision) -> None:
        """La sesion aplica el impacto a la ciudad y a los puntos; aqui se muestra la consecuencia."""
        self.sesion.aplicar()
        self.impacto = r.impacto
        self.animo = (r.impacto.score > 0) - (r.impacto.score < 0)
        # El texto cambia segun lo hallado (variante escrita en events.json o "Habias revisado: ...")
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
                self.app.estados.cambiar("mundo", fundido=True)   # noticia resuelta: de vuelta a la calle por la siguiente
                return
            self._preparar_turno()
            return
        self.impacto, self.animo = None, 1 if self.ciudad.score >= 0 else -1
        self.dialogo.set_texto(f"Termino la jornada en Ciudad Nova. Tu puntaje final es {self.ciudad.score}.", "Fin")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Volver al menu (Enter)", self._volver_al_menu,
                              atajo=pygame.K_RETURN)]

    def _volver_al_menu(self) -> None:
        self.app.partida = None    # la partida termino
        self.app.estados.cambiar("menu")

    # --- ciclo del estado ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if not self.interior:
                self.app.estados.cambiar("menu")
            elif self.fase == DECIDIENDO:
                self.app.estados.cambiar("mundo", fundido=True)   # salir a la calle sin decidir (la noticia sigue pendiente)
            elif self.fase == FIN:
                self._volver_al_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.dialogo.completar()  # saltar la animacion del texto
        if event.type == pygame.MOUSEBUTTONDOWN and RECT_DIALOGO.collidepoint(event.pos):
            self.dialogo.completar()
        if self.fase == DECIDIENDO:
            self._manejar_mapa(event)
            self._manejar_investigacion(event)
        for boton in list(self.botones):  # copia: un clic reemplaza self.botones
            if boton.handle_event(event):
                break

    def _manejar_investigacion(self, event: pygame.event.Event) -> None:
        """Investigar: clic sobre una zona de la tarjeta con pista, o su letra (A S D F G); el mouse
        encima la resalta."""
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
        if self.fase == PROPAGACION and self.animacion is not None:
            self.animacion.update(dt)
            narracion = self.animacion.narracion()
            if narracion != self._narracion:  # la caja de dialogo narra cada ola
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
            # Al decidir se ve la tarjeta de Civitas (sin titulo: "Rumor sobre..." delataria la noticia)
            titulo, texto = "", ""
        en_mapa = self.fase in (DECIDIENDO, CONSECUENCIA)
        dibujar_escena(pantalla, self.app.fuentes, self.app.temas.actual, self.personaje, self.animo,
                       self.ciudad.as_display_rows(), titulo, texto, self.impacto, self.dialogo, self.botones,
                       self.animacion if self.fase == PROPAGACION else None, self.zona,
                       self._nombre_zona(self.zona) if self.zona else "",
                       self._estado_mapa() if en_mapa else None,
                       EstadoTarjeta(self.arbol.event, self.investigacion, self._hover)
                       if self.fase == DECIDIENDO else None, AYUDA_INTERIOR if self.interior else AYUDA)
