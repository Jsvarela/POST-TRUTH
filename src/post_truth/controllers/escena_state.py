"""Controlador de la escena de dialogo (novela visual de decisiones).

Flujo por publicacion: DECIDIENDO (noticia + botones) -> [PROPAGACION] -> CONSECUENCIA
(mensaje + efecto en la ciudad) -> siguiente publicacion ... -> FIN. Todo el contenido sale
del DecisionTree cargado desde data/events.json; aqui no hay noticias fijas.

INVESTIGAR (energia): cada publicacion es una tarjeta de Civitas con zonas clicables (autor, fuente,
fecha, imagen, texto, estadisticas) que esconden pistas, y ademas deja EVIDENCIA en lugares del mapa
de la ciudad (un testigo, un documento, una grabacion). Hay UNA energia por publicacion (5) para
revisar la tarjeta y para viajar, y hay mas por revisar que energia: hay que elegir.

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

from post_truth.config import ANCHO, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, px
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.models.pistas import Investigacion, Pista
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import (REPORTAR, REPORTE_INFUNDADO, VERIFICAR, SimulacionDecision, es_falsa,
                                               fuerza_reportar, fuerza_verificar, mensaje_respaldo, reporte_rechazado,
                                               simular_decision)
from post_truth.views.componentes import Boton, CajaDialogo
from post_truth.views.escena_view import RECT_MAPA, RECT_TARJETA, dibujar_escena
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, zona_de_tecla, zona_en
from post_truth.views.tarjeta_civitas_view import EstadoTarjeta, pista_con_tecla, zona_en as zona_de_tarjeta

DECIDIENDO, PROPAGACION, CONSECUENCIA, FIN = "decidiendo", "propagacion", "consecuencia", "fin"
JUGADOR = "jugador"  # id del vertice del grafo social que representa al jugador
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
        # decision esperando a que termine la animacion: (nodo, impacto, aviso sobre el respaldo)
        self._pendiente: tuple[DecisionNode, Impact, str] | None = None
        self._narracion = ""
        # Mapa de la ciudad: la posicion del jugador dura toda la partida (no se reinicia por publicacion).
        self.mapa = GrafoCiudad()
        self.zona = ""
        self.ruta_vista: tuple[str, ...] = ()   # ultima ruta recorrida en esta publicacion (se resalta en el mapa)
        self.costo_ruta_vista = 0
        # Investigacion de la publicacion actual (energia, pistas y evidencias): se reinicia en cada una
        self.investigacion = Investigacion(())
        self._hover = None        # zona de la tarjeta bajo el mouse
        self._hover_zona = None   # zona del mapa bajo el mouse

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
        self.zona = self.mapa.zona_inicial
        self._cargar_evento()

    # --- mapa y viajes ------------------------------------------------------------------
    def _nombre_zona(self, id: str) -> str:
        return self.mapa.zona(id).nombre if id in self.mapa else id

    def _estado_mapa(self) -> EstadoMapa:
        decidiendo = self.fase == DECIDIENDO
        ruta, costo = self.ruta_vista, self.costo_ruta_vista
        if decidiendo and self._hover_zona not in (None, self.zona):   # vista previa de la ruta bajo el mouse
            previa = self.mapa.ruta(self.zona, self._hover_zona)
            if previa is not None:
                ruta, costo = previa.zonas, previa.costo
        return EstadoMapa(
            self.mapa, self.zona, self.mapa.costos_desde(self.zona),
            energia=self.investigacion.energia if decidiendo else None,
            ruta=ruta, costo_ruta=costo if ruta else None,
            pendientes=self.investigacion.lugares_pendientes() if decidiendo else set(),
            revisadas=self.investigacion.lugares_revisados(),
            hover=self._hover_zona if decidiendo else None, teclas=decidiendo,
            mostrar_ayuda=decidiendo)   # la franja de ayuda solo sirve mientras se decide

    def _viajar(self, destino: str) -> None:
        """Ir a una zona cualquiera: cuesta la distancia del camino mas corto (Dijkstra) y, si la
        energia no alcanza, no se mueve ni se cobra. Al llegar se revela la evidencia que haya alli."""
        if self.fase != DECIDIENDO or destino == self.zona or destino not in self.mapa:
            return
        ruta = self.mapa.ruta(self.zona, destino)
        nombre = self._nombre_zona(destino)
        if ruta is None:
            self._decir_en_sitio(f"No hay camino hasta {nombre}.")
            return
        if not self.investigacion.viajar(ruta.costo):
            self._decir_en_sitio(f"No te alcanza la energia: ir a {nombre} cuesta {ruta.costo} y te quedan "
                                 f"{self.investigacion.energia}. Decide con lo que sabes o revisa algo mas barato.")
            return
        self.zona, self.ruta_vista, self.costo_ruta_vista = destino, ruta.zonas, ruta.costo
        camino = " > ".join(self._nombre_zona(z) for z in ruta.zonas)
        aviso = f"Viajas a {nombre} por {camino} (costo {ruta.costo})."
        evidencia = self.investigacion.revelar_evidencia(destino)
        if evidencia is not None:
            aviso += f" {evidencia.titulo}: {evidencia.hallazgo}"
        elif self.investigacion.evidencia_en(destino) is not None:
            aviso += " Ya habias revisado lo de este lugar."
        else:
            aviso += " Aqui no hay nada de esta noticia."
        self._decir_en_sitio(aviso)

    def _manejar_mapa(self, event: pygame.event.Event) -> None:
        """Viajar: clic sobre una zona del mapa o su letra (Q W E R T); el mouse encima muestra la ruta."""
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
        self.fase, self.impacto, self.animo = DECIDIENDO, None, 0
        evento = self.arbol.event
        self.investigacion = Investigacion(evento.clues, evidencias=evento.evidences)  # energia completa
        self._hover = self._hover_zona = None
        self.ruta_vista, self.costo_ruta_vista = (), 0
        self.dialogo.set_texto(evento.content, "Civitas")
        # Si el jugador ya esta parado donde la noticia dejo evidencia, se revela sola (no cuesta nada)
        evidencia = self.investigacion.revelar_evidencia(self.zona)
        if evidencia is not None:
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
        """Revisa una pista de la tarjeta: gasta energia, revela el hallazgo y marca la zona."""
        if self.fase != DECIDIENDO:
            return
        r = self.investigacion.investigar(pista.id)
        if r.estado == "sin_energia":
            aviso = (f"No te queda energia para revisar eso: cuesta {pista.costo} y tienes "
                     f"{self.investigacion.energia}. Decide con lo que sabes, o relee una pista ya revisada.")
        else:
            aviso = f"{pista.titulo}: {pista.hallazgo}"   # "repetida" no cuesta nada: se relee
        self._decir_en_sitio(aviso)

    def _decidir(self, nodo: DecisionNode) -> None:
        if self.fase != DECIDIENDO:
            return
        # accumulated_impact recorre la raiz hasta `nodo` (DFS, O(n) en nodos del evento) y suma
        # el efecto de la publicacion (root_effect) mas el de la decision: es la cadena de causas.
        bruto = self.arbol.accumulated_impact(nodo.node_id)
        impacto = bruto.scaled_for_role(self.personaje.rol)  # el rol cambia el resultado
        # Verificar y Reportar rinden segun el respaldo reunido (0 nada, 1 tarjeta, 2 evidencia de campo).
        # Solo se atenuan los BENEFICIOS; los perjuicios de equivocarse no se abaratan.
        respaldo = self.investigacion.respaldo(nodo.tipo) if nodo.tipo in (VERIFICAR, REPORTAR) else 2
        if nodo.tipo == VERIFICAR:
            impacto = impacto.atenuar_beneficios(fuerza_verificar(respaldo))
        elif nodo.tipo == REPORTAR:
            impacto = impacto.atenuar_beneficios(fuerza_reportar(respaldo))
            if reporte_rechazado(respaldo):
                impacto = impacto + REPORTE_INFUNDADO   # reportar sin ninguna prueba cuesta confianza
        aviso = mensaje_respaldo(nodo.tipo, respaldo)
        simulacion = self._simular(nodo, respaldo)
        if simulacion is None:
            self._mostrar_consecuencia(nodo, impacto, aviso)
            return
        self._pendiente = (nodo, impacto, aviso)
        self.animacion = AnimacionPropagacion(self.grafo, simulacion)
        self.fase = PROPAGACION
        self.animo = 0
        self._narracion = self.animacion.narracion()
        self.dialogo.set_texto(self._narracion, "Civitas")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Saltar animacion (Enter)",
                              self.animacion.saltar, atajo=pygame.K_RETURN)]

    def _simular(self, nodo: DecisionNode, respaldo: int) -> SimulacionDecision | None:
        """Propagacion que desencadena la decision, o None si no mueve la publicacion (Ignorar o un
        reporte rechazado). El autor original de la noticia se sortea entre los demas ciudadanos."""
        if not nodo.tipo:
            return None
        autor = self.rng.choice([c.id for c in self.grafo.vertices() if c.id != JUGADOR])
        return simular_decision(self.grafo, nodo.tipo, es_falsa(self.arbol.event.truth_level),
                                JUGADOR, autor, self.rng, respaldo=respaldo)

    def _mostrar_consecuencia(self, nodo: DecisionNode, impacto: Impact, aviso: str = "") -> None:
        self.impacto = impacto
        self.ciudad.apply(impacto)
        self.animo = (impacto.score > 0) - (impacto.score < 0)
        self.fase = CONSECUENCIA
        # El texto cambia segun lo hallado (variante escrita en events.json o "Habias revisado: ...")
        mensaje = nodo.consecuencia(self.investigacion.pistas_descubiertas()) or "Nada cambia por ahora."
        self.dialogo.set_texto(f"{mensaje}\n{aviso}" if aviso else mensaje, "Consecuencia")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Continuar (Enter)",
                              self._continuar, atajo=pygame.K_RETURN)]

    def _terminar_propagacion(self) -> None:
        """Pasa de la animacion a las consecuencias: efecto del arbol + efecto de la propagacion."""
        assert self.animacion is not None and self._pendiente is not None
        nodo, impacto_arbol, aviso = self._pendiente
        impacto = impacto_arbol + self.animacion.resultado.impacto()
        self.animacion, self._pendiente = None, None
        self._mostrar_consecuencia(nodo, impacto, aviso)

    def _continuar(self) -> None:
        self.indice += 1
        if self.indice < len(self.arboles):
            self._cargar_evento()
            return
        self.fase, self.impacto, self.animo = FIN, None, 1 if self.ciudad.score >= 0 else -1
        self.dialogo.set_texto(f"Termino la jornada en Ciudad Nova. Tu puntaje final es {self.ciudad.score}.", "Fin")
        self.botones = [Boton(RECT_BOTON_CENTRAL, "Volver al menu (Enter)",
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
                       if self.fase == DECIDIENDO else None)
