"""Controlador de la escena de dialogo (novela visual de decisiones).

Flujo por publicacion: DECIDIENDO (noticia + botones) -> [PROPAGACION] -> CONSECUENCIA
(mensaje + efecto en la ciudad) -> siguiente publicacion ... -> FIN. Todo el contenido sale
del DecisionTree cargado desde data/events.json; aqui no hay noticias fijas.

ZONAS Y RONDAS: cada noticia ocurre en una zona del GrafoCiudad y el jugador esta en otra (o en la
misma). Moverse a una zona vecina (clic en el mapa o Q W E R) y cada decision cuestan una RONDA, y en
cada ronda los rumores sin atender se expanden un anillo (RumoresCiudad). Verificar y Reportar
exigen estar en la zona de la noticia; Compartir e Ignorar se pueden hacer desde cualquier parte.

PROPAGACION solo ocurre si la decision mueve la publicacion por el grafo social (Compartir,
Verificar, Reportar; Ignorar no). El efecto sobre los indicadores se aplica DESPUES de la
animacion, para que el jugador vea primero como viaja la noticia y luego sus consecuencias.
"""
import random

import pygame

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import (COMPARTIR, REPORTAR, VERIFICAR, SimulacionDecision, es_falsa,
                                               simular_decision)
from post_truth.structures.rumores_ciudad import RumoresCiudad
from post_truth.views.componentes import Boton, CajaDialogo
from post_truth.views.escena_view import RECT_MAPA, dibujar_escena
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, zona_en

DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN = "decidiendo", "propagacion", "consecuencia", "fin"
JUGADOR = "jugador"  # id del vertice del grafo social que representa al jugador
RECT_DIALOGO = pygame.Rect(24, 404, 976, 132)
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]
TECLAS_MOVER = [pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r]  # ir a la 1.a, 2.a, 3.a o 4.a zona vecina
Y_BOTONES, ALTO_BOTONES, MARGEN, SEPARACION = 546, 62, 24, 14
TIPOS_EN_SITIO = {VERIFICAR, REPORTAR}  # acciones que exigen estar en la zona de la noticia
# Premio por ir a una zona infectada y desmentir el rumor (accion responsable: suma confianza y puntos)
DESMENTIR_PREMIO = Impact(verified_information=4, trust=3, score=4)


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
        # Ciudad: la zona del jugador, los rumores y el contador de rondas duran toda la partida.
        self.mapa = GrafoCiudad()
        self.rumores = RumoresCiudad(self.mapa)
        self.zona = ""
        self.ronda = 0
        self._titulos: dict[str, str] = {}

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
        self.mapa = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        self.rumores = RumoresCiudad(self.mapa)
        self.zona, self.ronda = self.mapa.zona_inicial, 0
        self._titulos = {a.event.event_id: a.event.title for a in self.arboles}
        self._cargar_evento()

    # --- zonas y rumores ----------------------------------------------------------------
    def _nombre_zona(self, id: str) -> str:
        return self.mapa.zona(id).nombre if id in self.mapa else id

    def _puede(self, nodo: DecisionNode) -> bool:
        """Verificar y Reportar se hacen en el lugar de la noticia; el resto, desde cualquier zona."""
        return nodo.tipo not in TIPOS_EN_SITIO or self.zona == self.arbol.event.zone

    def _estado_mapa(self) -> EstadoMapa:
        decidiendo = self.fase == DECIDIENDO
        return EstadoMapa(
            self.mapa, self.zona, zona_noticia=self.arbol.event.zone if decidiendo else "",
            infectadas=self.rumores.zonas_infectadas(), en_riesgo=self.rumores.zonas_en_riesgo(),
            alcanzables=self.mapa.vecinos(self.zona) if decidiendo else [])

    def _pasar_ronda(self) -> tuple[Impact, str]:
        """Una ronda: los rumores sin atender se expanden un anillo (BFS por niveles sobre el grafo
        de la ciudad) y cada zona infectada cuesta una penalizacion pequena. Devuelve ese costo y
        un aviso para el dialogo."""
        self.ronda += 1
        nuevas = self.rumores.avanzar_ronda()
        por_rumor: dict[str, list[str]] = {}
        for rumor_id, zona in nuevas:
            por_rumor.setdefault(rumor_id, []).append(self._nombre_zona(zona))
        partes = [f"El rumor \u00ab{self._titulos.get(r, r)}\u00bb llega a {', '.join(z)}." for r, z in por_rumor.items()]
        if not partes and self.rumores.visibles():
            partes = ["Los rumores siguen activos."]
        return self.rumores.penalizacion(), " ".join(partes[:2])

    def _mover(self, destino: str) -> None:
        if self.fase != DECIDIENDO or destino not in self.mapa.vecinos(self.zona):
            return
        self.zona = destino
        costo, aviso = self._pasar_ronda()
        self.ciudad.apply(costo)
        self._decir_en_sitio(f"Vas a {self._nombre_zona(destino)}. {aviso}".strip())
        self._construir_botones()

    def _desmentir(self) -> None:
        """Estando en una zona infectada: elimina ese rumor (premio por actuar con responsabilidad)
        y cuesta una ronda."""
        if self.fase != DECIDIENDO:
            return
        rumor = self.rumores.rumor_en(self.zona, excluir=self.arbol.event.event_id)
        if rumor is None:
            return
        self.rumores.resolver(rumor.id)
        costo, aviso = self._pasar_ronda()
        self.ciudad.apply(DESMENTIR_PREMIO + costo)
        titulo = self._titulos.get(rumor.id, rumor.id)
        self._decir_en_sitio(f"Desmientes el rumor \u00ab{titulo}\u00bb en {self._nombre_zona(self.zona)}. {aviso}".strip())
        self._construir_botones()

    def _decir_en_sitio(self, aviso: str) -> None:
        """Muestra la noticia y debajo el aviso, sin volver a animar el texto (ya se leyo)."""
        self.dialogo.set_texto(f"{self.arbol.event.content}\n{aviso}", "Civitas")
        self.dialogo.completar()

    # --- transiciones -------------------------------------------------------------------
    def _cargar_evento(self) -> None:
        self.fase, self.impacto, self.animo = DECIDIENDO, None, 0
        evento = self.arbol.event
        self.dialogo.set_texto(evento.content, "Civitas")
        # Una noticia falsa es un rumor desde que aparece, pero el mapa no lo muestra hasta que
        # empieza a correr (si no, delataria cual es falsa sin investigar).
        if evento.zone and es_falsa(evento.truth_level):
            self.rumores.nacer(evento.event_id, evento.zone)
        self._construir_botones()

    def _construir_botones(self) -> None:
        """Un boton por rama del evento (las acciones cambian segun la noticia: "Verificar",
        "Buscar video completo", ...) mas "Desmentir aqui" si la zona actual tiene un rumor viejo.
        Las acciones que exigen estar en la zona de la noticia salen apagadas si no estas ahi."""
        evento = self.arbol.event
        ramas = self.arbol.root.children[:4]
        desmentible = self.rumores.rumor_en(self.zona, excluir=evento.event_id)
        rects = _rects_botones(len(ramas) + (1 if desmentible else 0))
        botones: list[Boton] = []
        for i, (rect, nodo) in enumerate(zip(rects, ramas)):
            ok = self._puede(nodo)
            texto = f"{i + 1}. {nodo.label}" + ("" if ok else f" (ir a {self._nombre_zona(evento.zone)})")
            boton = Boton(rect, texto, lambda n=nodo: self._decidir(n), atajo=ATAJOS[i])
            boton.habilitado = ok
            botones.append(boton)
        if desmentible:
            botones.append(Boton(rects[-1], f"{len(ramas) + 1}. Desmentir aqui", self._desmentir,
                                 atajo=ATAJOS[len(ramas)]))
        self.botones = botones

    def _decidir(self, nodo: DecisionNode) -> None:
        if self.fase != DECIDIENDO or not self._puede(nodo):
            return
        evento = self.arbol.event
        if nodo.tipo in TIPOS_EN_SITIO:
            self.rumores.resolver(evento.event_id)   # atendido en el lugar: el rumor muere
        elif nodo.tipo == COMPARTIR:
            self.rumores.ampliar(evento.event_id)    # compartirlo lo extiende un anillo de golpe
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
        # Decidir tambien es una ronda: los rumores que quedaron sin atender avanzan y se cobran
        costo, aviso = self._pasar_ronda()
        impacto = impacto + costo
        self.impacto = impacto
        self.ciudad.apply(impacto)
        self.animo = (impacto.score > 0) - (impacto.score < 0)
        self.fase = CONSECUENCIA
        mensaje = nodo.description or "Nada cambia por ahora."
        self.dialogo.set_texto(f"{mensaje}\n{aviso}" if aviso else mensaje, "Consecuencia")
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
        pendientes = len(self.rumores.activos())
        extra = f" Rumores sin atender: {pendientes}." if pendientes else " No quedan rumores activos."
        self.dialogo.set_texto(f"Termino la jornada en Ciudad Nova. Tu puntaje final es {self.ciudad.score}.{extra}",
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
        if self.fase == DECIDIENDO:
            self._manejar_movimiento(event)
        for boton in list(self.botones):  # copia: un clic reemplaza self.botones
            if boton.handle_event(event):
                break

    def _manejar_movimiento(self, event: pygame.event.Event) -> None:
        """Ir a una zona vecina: clic sobre ella en el minimapa, o su letra (Q W E R) en el teclado."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zona = zona_en(self._estado_mapa(), RECT_MAPA, event.pos)
            if zona is not None:
                self._mover(zona)
        elif event.type == pygame.KEYDOWN and event.key in TECLAS_MOVER:
            i = TECLAS_MOVER.index(event.key)
            vecinos = self.mapa.vecinos(self.zona)
            if i < len(vecinos):
                self._mover(vecinos[i])

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
            texto = (f"La noticia viene de: {self._nombre_zona(self.arbol.event.zone)}.\n"
                     "Verificar y Reportar: solo en esa zona.\n"
                     "Moverse (mapa o Q W E R) cuesta una ronda y los rumores avanzan.\n"
                     f"Tu rol: {self.personaje.rol.value}.")
        en_mapa = self.fase in (DECIDIENDO, CONSECUENCIA)
        dibujar_escena(pantalla, self.app.fuentes, self.app.temas.actual, self.personaje, self.animo,
                       self.ciudad.as_display_rows(), titulo, texto, self.impacto, self.dialogo, self.botones,
                       self.animacion if self.fase == PROPAGACION else None, self.zona,
                       self._nombre_zona(self.zona) if self.zona else "",
                       self._estado_mapa() if en_mapa else None)
