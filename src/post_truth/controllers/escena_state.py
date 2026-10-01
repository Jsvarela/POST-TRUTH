"""Controlador de la escena de dialogo (novela visual de decisiones).

Flujo por publicacion: DECIDIENDO (noticia + botones) -> [PROPAGACION] -> CONSECUENCIA
(mensaje + efecto en la ciudad) -> siguiente publicacion ... -> FIN. Todo el contenido sale
del DecisionTree cargado desde data/events.json; aqui no hay noticias fijas.

PROPAGACION solo ocurre si la decision mueve la publicacion por el grafo social (Compartir,
Verificar, Reportar; Ignorar no). El efecto sobre los indicadores se aplica DESPUES de la
animacion, para que el jugador vea primero como viaja la noticia y luego sus consecuencias.
"""
import random

import pygame

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_SOCIAL
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import SimulacionDecision, es_falsa, simular_decision
from post_truth.views.componentes import Boton, CajaDialogo
from post_truth.views.escena_view import dibujar_escena
from post_truth.views.grafo_view import AnimacionPropagacion

DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN = "decidiendo", "propagacion", "consecuencia", "fin"
JUGADOR = "jugador"  # id del vertice del grafo social que representa al jugador
RECT_DIALOGO = pygame.Rect(24, 404, 976, 124)
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]
Y_BOTONES, ALTO_BOTONES, MARGEN, SEPARACION = 540, 62, 24, 14


def _rects_botones(n: int) -> list[pygame.Rect]:
    """Reparte `n` botones a lo ancho de la pantalla (3 o 4 segun las ramas del evento)."""
    ancho = (RECT_DIALOGO.width - SEPARACION * (n - 1)) // n
    return [pygame.Rect(MARGEN + i * (ancho + SEPARACION), Y_BOTONES, ancho, ALTO_BOTONES) for i in range(n)]


class EscenaState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()  # inyectable en pruebas para fijar el orden
        self.ciudad = CityState()
        self.arboles: list[DecisionTree] = []
        self.indice = 0
        self.fase = DECIDIENDO
        self.dialogo = CajaDialogo(RECT_DIALOGO)
        self.botones: list[Boton] = []
        self.impacto: Impact | None = None  # efecto ya escalado por rol, para mostrarlo
        self.animo = 0                       # reaccion del personaje: -1, 0, 1
        # Un mismo grafo social dura toda la partida: lo que se corta o se frena con
        # Verificar/Reportar sigue cortado/frenado en las publicaciones siguientes.
        self.grafo = GrafoSocial()
        self.animacion: AnimacionPropagacion | None = None
        self._pendiente: tuple[DecisionNode, Impact] | None = None  # decision esperando a que termine la animacion
        self._narracion = ""

    @property
    def personaje(self) -> Personaje:
        # Respaldo para poder abrir la escena directamente (pruebas) sin pasar por la seleccion.
        return getattr(self.app, "personaje", None) or Personaje(Role.CITIZEN, Genero.MUJER)

    @property
    def arbol(self) -> DecisionTree:
        return self.arboles[self.indice]

    def al_entrar(self) -> None:
        self.ciudad = CityState()
        self.arboles = load_trees(RUTA_EVENTOS)
        self.rng.shuffle(self.arboles)  # el orden de publicaciones cambia entre partidas
        self.indice = 0
        self.grafo = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        self.grafo.cambiar_rol(JUGADOR, self.personaje.rol)  # el rol elegido define cuanto amplifica al compartir
        self.animacion = None
        self._cargar_evento()

    # --- transiciones -------------------------------------------------------------------
    def _cargar_evento(self) -> None:
        self.fase, self.impacto, self.animo = DECIDIENDO, None, 0
        evento = self.arbol.event
        self.dialogo.set_texto(evento.content, "Civitas")
        # Un boton por rama del evento: las acciones cambian segun la noticia
        # ("Verificar", "Buscar video completo", ...), por eso salen del arbol y no de un enum.
        ramas = self.arbol.root.children[: len(ATAJOS)]
        self.botones = [Boton(rect, f"{i + 1}. {nodo.label}", lambda n=nodo: self._decidir(n), atajo=ATAJOS[i])
                        for i, (rect, nodo) in enumerate(zip(_rects_botones(len(ramas)), ramas))]

    def _decidir(self, nodo: DecisionNode) -> None:
        if self.fase != DECIDIENDO:
            return
        # accumulated_impact recorre la raiz hasta `nodo` (DFS, O(n) en nodos del evento) y suma
        # el efecto de la publicacion (root_effect) mas el de la decision: es la cadena de causas.
        bruto = self.arbol.accumulated_impact(nodo.node_id)
        impacto = bruto.scaled_for_role(self.personaje.rol)  # el rol cambia el resultado
        simulacion = self._simular(nodo)
        if simulacion is None:
            self._mostrar_consecuencia(nodo, impacto)
            return
        self._pendiente = (nodo, impacto)
        self.animacion = AnimacionPropagacion(self.grafo, simulacion)
        self.fase = PROPAGACION
        self.animo = 0
        self._narracion = self.animacion.narracion()
        self.dialogo.set_texto(self._narracion, "Civitas")
        self.botones = [Boton(pygame.Rect(362, Y_BOTONES, 300, ALTO_BOTONES), "Saltar animacion (Enter)",
                              self.animacion.saltar, atajo=pygame.K_RETURN)]

    def _simular(self, nodo: DecisionNode) -> SimulacionDecision | None:
        """Propagacion que desencadena la decision, o None si no mueve la publicacion.
        El autor original de la noticia se sortea entre los demas ciudadanos."""
        if not nodo.tipo:
            return None
        autor = self.rng.choice([c.id for c in self.grafo.vertices() if c.id != JUGADOR])
        return simular_decision(self.grafo, nodo.tipo, es_falsa(self.arbol.event.truth_level),
                                JUGADOR, autor, self.rng)

    def _mostrar_consecuencia(self, nodo: DecisionNode, impacto: Impact) -> None:
        self.impacto = impacto
        self.ciudad.apply(impacto)
        self.animo = (impacto.score > 0) - (impacto.score < 0)
        self.fase = CONSECUENCIA
        self.dialogo.set_texto(nodo.description or "Nada cambia por ahora.", "Consecuencia")
        self.botones = [Boton(pygame.Rect(362, Y_BOTONES, 300, ALTO_BOTONES), "Continuar (Enter)",
                              self._continuar, atajo=pygame.K_RETURN)]

    def _terminar_propagacion(self) -> None:
        """Pasa de la animacion a las consecuencias: efecto del arbol + efecto de la propagacion."""
        assert self.animacion is not None and self._pendiente is not None
        nodo, impacto_arbol = self._pendiente
        impacto = impacto_arbol + self.animacion.resultado.impacto()
        self.animacion, self._pendiente = None, None
        self._mostrar_consecuencia(nodo, impacto)

    def _continuar(self) -> None:
        self.indice += 1
        if self.indice < len(self.arboles):
            self._cargar_evento()
            return
        self.fase, self.impacto, self.animo = FIN, None, 1 if self.ciudad.score >= 0 else -1
        self.dialogo.set_texto(f"Termino la jornada en Ciudad Nova. Tu puntaje final es {self.ciudad.score}.",
                               "Fin")
        self.botones = [Boton(pygame.Rect(362, Y_BOTONES, 300, ALTO_BOTONES), "Volver al menu (Enter)",
                              lambda: self.app.estados.cambiar("menu"), atajo=pygame.K_RETURN)]

    # --- ciclo del estado ---------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.estados.cambiar("menu")
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.dialogo.completar()  # saltar la animacion del texto
        if event.type == pygame.MOUSEBUTTONDOWN and RECT_DIALOGO.collidepoint(event.pos):
            self.dialogo.completar()
        for boton in list(self.botones):  # copia: un clic reemplaza self.botones
            if boton.handle_event(event):
                break

    def update(self, dt: float) -> None:
        self.dialogo.update(dt)
        if self.fase == PROPAGACION and self.animacion is not None:
            self.animacion.update(dt)
            narracion = self.animacion.narracion()
            if narracion != self._narracion:  # la caja de dialogo narra cada ola
                self._narracion = narracion
                self.dialogo.set_texto(narracion, "Civitas")
            if self.animacion.terminada and self.botones[0].texto.startswith("Saltar"):
                self.botones = [Boton(pygame.Rect(362, Y_BOTONES, 300, ALTO_BOTONES), "Ver consecuencias (Enter)",
                                      self._terminar_propagacion, atajo=pygame.K_RETURN)]

    def draw(self, pantalla: pygame.Surface) -> None:
        if self.fase == FIN:
            titulo, texto = "Fin de la jornada", "Gracias por cuidar Ciudad Nova."
        elif self.fase == CONSECUENCIA:
            titulo, texto = "Consecuencias en Ciudad Nova", ""
        else:
            titulo = self.arbol.event.title
            texto = ("Una publicacion circula en Civitas. Decide que hacer con ella.\n\n"
                     f"Tu rol: {self.personaje.rol.value}. {self.personaje.descripcion_rol}")
        dibujar_escena(pantalla, self.app.fuentes, self.app.temas.actual, self.personaje, self.animo,
                       self.ciudad.as_display_rows(), titulo, texto, self.impacto, self.dialogo, self.botones,
                       self.animacion if self.fase == PROPAGACION else None)
