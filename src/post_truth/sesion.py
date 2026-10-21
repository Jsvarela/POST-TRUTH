"""Sesion de partida: el estado y las reglas del juego, sin pygame ni vistas (logica pura y serializable).

PROBLEMA QUE RESUELVE
    Todo lo que vive "en la partida" (ciudad, jugadores, zona, hallazgos, puntos, publicacion actual,
    de quien es el turno) estaba mezclado con botones y animaciones en EscenaState. Para el multijugador
    cliente-servidor el servidor debe guardar y reenviar ese estado, asi que aqui vive solo el modelo y el
    controlador (EscenaState) se limita a traducir eventos de pygame a llamadas de esta clase.

COMPARTIDO vs INDIVIDUAL
    Compartido: ciudad, grafo social (lo que se corta o frena persiste), publicacion actual y rng.
    Individual (`Jugador`): personaje/rol, zona, hallazgos (su `Investigacion`) y puntos.

REGLA DE TURNOS
    En cada publicacion decide cada jugador una vez, en orden. Empieza el jugador `indice % n` (rota), asi que el
    que abre la ronda cambia de una publicacion a otra. Cada uno empieza la publicacion sin hallazgos y
    conserva su zona. Con un jugador es exactamente el flujo de siempre.

OPERACIONES (devuelven un resultado, no lanzan excepciones por usarse fuera de turno)
    investigar(jugador, pista) -> ResultadoInvestigar
    viajar(jugador, zona)      -> ResultadoViaje
    decidir(jugador, accion)   -> ResultadoDecision   (calcula y deja PENDIENTE; el grafo social ya cambia)
    aplicar()                  -> suma el impacto a la ciudad y a los puntos del jugador (fase CONSECUENCIA)
    continuar()                -> siguiente jugador / siguiente publicacion / FIN
    `decidir` y `aplicar` van separadas para que la animacion de la propagacion se vea ANTES de que cambien los
    indicadores, como siempre.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Sequence

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact
from post_truth.models.personaje import Personaje
from post_truth.models.pistas import Evidencia, Investigacion, Pista
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import Ciudadano, GrafoSocial
from post_truth.structures.propagacion import (REPORTAR, REPORTE_INFUNDADO, VERIFICAR, SimulacionDecision, es_falsa,
                                               fuerza_reportar, fuerza_verificar, mensaje_respaldo, reporte_rechazado,
                                               simular_decision)

DECIDIENDO, CONSECUENCIA, FIN = "decidiendo", "consecuencia", "fin"
JUGADOR = "jugador"   # vertice del grafo social del primer jugador; los demas son jugador2, jugador3...
MIN_JUGADORES, MAX_JUGADORES = 1, 4
VERSION = 1


@dataclass
class Jugador:
    id: str                      # vertice del grafo social
    personaje: Personaje
    zona: str
    puntos: int = 0
    investigacion: Investigacion = field(default_factory=lambda: Investigacion(()))

    @property
    def rol(self):
        return self.personaje.rol


@dataclass(frozen=True)
class ResultadoInvestigar:
    ok: bool
    motivo: str = ""     # "" | no_es_su_turno | fuera_de_fase | decision_pendiente
    estado: str = ""     # nueva | repetida (los de Investigacion.investigar)
    pista: Pista | None = None


@dataclass(frozen=True)
class ResultadoViaje:
    ok: bool
    motivo: str = ""     # "" | no_es_su_turno | fuera_de_fase | decision_pendiente | misma_zona | zona_desconocida | sin_camino
    destino: str = ""
    ruta: tuple[str, ...] = ()
    evidencia: Evidencia | None = None   # la que se revelo al llegar
    revisada: bool = False               # habia evidencia aqui pero ya se habia revisado


@dataclass(frozen=True)
class ResultadoDecision:
    ok: bool
    motivo: str = ""
    jugador: str = ""
    nodo: DecisionNode | None = None
    impacto: Impact = Impact()           # total: efecto del arbol (por rol y respaldo) + el de la propagacion
    aviso: str = ""                      # como peso el respaldo en Verificar/Reportar
    simulacion: SimulacionDecision | None = None   # None: no mueve la publicacion por el grafo (no se anima)


class PartidaSesion:
    def __init__(self, jugadores: Sequence[Jugador], arboles: list[DecisionTree], grafo: GrafoSocial,
                 mapa: GrafoCiudad, rng: random.Random, ciudad: CityState | None = None) -> None:
        _validar_cantidad(len(jugadores))
        if not arboles:
            raise ValueError("La partida necesita al menos una publicacion")
        self.jugadores = list(jugadores)
        self.arboles = arboles          # mutable a proposito: las pruebas reordenan las publicaciones
        self.grafo, self.mapa, self.rng = grafo, mapa, rng
        self.ciudad = ciudad if ciudad is not None else CityState()
        self.indice = 0
        self.turno = 0                  # cuantos jugadores ya decidieron en esta publicacion
        self.fase = DECIDIENDO
        self.pendiente: ResultadoDecision | None = None

    @classmethod
    def nueva(cls, personajes: Sequence[Personaje], arboles: list[DecisionTree], grafo: GrafoSocial,
              mapa: GrafoCiudad, rng: random.Random) -> "PartidaSesion":
        _validar_cantidad(len(personajes))
        jugadores = []
        for i, personaje in enumerate(personajes):
            id = JUGADOR if i == 0 else f"{JUGADOR}{i + 1}"
            if i:
                _clonar_vertice(grafo, id)
            grafo.cambiar_rol(id, personaje.rol)   # el rol define cuanto amplifica al compartir
            jugadores.append(Jugador(id, personaje, mapa.zona_inicial))
        sesion = cls(jugadores, arboles, grafo, mapa, rng)
        sesion.abrir_evento()
        return sesion

    # --- consultas ------------------------------------------------------------------------
    @property
    def arbol(self) -> DecisionTree:
        return self.arboles[min(self.indice, len(self.arboles) - 1)]   # en FIN se queda en la ultima

    @property
    def jugador_actual(self) -> Jugador:
        return self.jugadores[(self.indice + self.turno) % len(self.jugadores)]

    @property
    def terminada(self) -> bool:
        return self.fase == FIN

    def jugador(self, id: str) -> Jugador:
        for j in self.jugadores:
            if j.id == id:
                return j
        raise KeyError(f"No existe el jugador: {id}")

    def _turno_de(self, id: str) -> tuple[Jugador, str]:
        """El jugador y, si no puede actuar ahora, el motivo ("" si puede)."""
        j = self.jugador(id)
        if self.fase != DECIDIENDO:
            return j, "fuera_de_fase"
        if self.pendiente is not None:
            return j, "decision_pendiente"
        if j is not self.jugador_actual:
            return j, "no_es_su_turno"
        return j, ""

    # --- operaciones ----------------------------------------------------------------------
    def investigar(self, jugador: str, pista: Pista | str) -> ResultadoInvestigar:
        """Revisa una pista de la tarjeta (gratis; una ya revelada se relee)."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoInvestigar(False, motivo)
        r = j.investigacion.investigar(pista.id if isinstance(pista, Pista) else pista)
        return ResultadoInvestigar(True, "", r.estado, r.pista)

    def viajar(self, jugador: str, zona: str) -> ResultadoViaje:
        """Ir a cualquier zona por el camino mas corto (Dijkstra, GrafoCiudad.ruta). Al llegar se revela la
        evidencia de la publicacion."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoViaje(False, motivo, zona)
        if zona == j.zona:
            return ResultadoViaje(False, "misma_zona", zona)
        if zona not in self.mapa:
            return ResultadoViaje(False, "zona_desconocida", zona)
        ruta = self.mapa.ruta(j.zona, zona)
        if ruta is None:
            return ResultadoViaje(False, "sin_camino", zona)
        j.zona = zona
        evidencia = j.investigacion.revelar_evidencia(zona)
        revisada = evidencia is None and j.investigacion.evidencia_en(zona) is not None
        return ResultadoViaje(True, "", zona, ruta.zonas, evidencia, revisada)

    # --- mundo caminable: la sesion sigue siendo la fuente de verdad -------------------------
    @property
    def zona_noticia(self) -> str:
        """Lugar donde ocurre la publicacion activa: la zona de su imagen (cada noticia tiene una)."""
        imagen = self.arbol.event.image
        return imagen.motivo if imagen is not None else self.mapa.zona_inicial

    def llegar(self, jugador: str, zona: str) -> None:
        """El jugador del mundo llego a la plaza `zona`: la sesion queda en la misma zona (sin revelar nada)."""
        if zona not in self.mapa:
            raise KeyError(f"Zona desconocida: {zona}")
        self.jugador(jugador).zona = zona

    def buscar_evidencia(self, jugador: str) -> Evidencia | None:
        """Revela la evidencia de la publicacion activa que hay en la zona del jugador. None si no hay, si ya se
        habia revelado o si no es su turno."""
        j, motivo = self._turno_de(jugador)
        return None if motivo else j.investigacion.revelar_evidencia(j.zona)

    def decidir(self, jugador: str, accion: DecisionNode | str) -> ResultadoDecision:
        """Elige una rama de la publicacion. El impacto del arbol se suma a lo largo del camino (DFS), se escala
        por el rol y, en Verificar/Reportar, segun el respaldo reunido. Si la decision mueve la publicacion por
        el grafo social, aqui se simula (y el grafo cambia) pero los indicadores no se tocan hasta `aplicar`."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoDecision(False, motivo, jugador)
        nodo = accion if isinstance(accion, DecisionNode) else self.arbol.find(accion)
        if nodo is None:
            raise KeyError(f"No existe la decision: {accion}")
        impacto = self.arbol.accumulated_impact(nodo.node_id).scaled_for_role(j.rol)
        # Solo se atenuan los BENEFICIOS; los perjuicios de equivocarse no se abaratan.
        respaldo = j.investigacion.respaldo(nodo.tipo) if nodo.tipo in (VERIFICAR, REPORTAR) else 2
        if nodo.tipo == VERIFICAR:
            impacto = impacto.atenuar_beneficios(fuerza_verificar(respaldo))
        elif nodo.tipo == REPORTAR:
            impacto = impacto.atenuar_beneficios(fuerza_reportar(respaldo))
            if reporte_rechazado(respaldo):
                impacto = impacto + REPORTE_INFUNDADO   # reportar sin ninguna prueba cuesta confianza
        simulacion = self._simular(j, nodo, respaldo)
        if simulacion is not None:
            impacto = impacto + simulacion.resultado.impacto()
        self.pendiente = ResultadoDecision(True, "", j.id, nodo, impacto, mensaje_respaldo(nodo.tipo, respaldo),
                                           simulacion)
        return self.pendiente

    def _simular(self, j: Jugador, nodo: DecisionNode, respaldo: int) -> SimulacionDecision | None:
        if not nodo.tipo:
            return None     # una respuesta sin tipo (opinion) no mueve la publicacion por el grafo
        propios = {x.id for x in self.jugadores}
        autor = self.rng.choice([c.id for c in self.grafo.vertices() if c.id not in propios])
        return simular_decision(self.grafo, nodo.tipo, es_falsa(self.arbol.event.truth_level), j.id, autor,
                                self.rng, respaldo=respaldo)

    def aplicar(self) -> ResultadoDecision:
        """Cierra la decision pendiente: el impacto entra a la ciudad y a los puntos de quien decidio."""
        r = self.pendiente
        if r is None:
            raise ValueError("No hay una decision pendiente")
        self.ciudad.apply(r.impacto)
        self.jugador(r.jugador).puntos += r.impacto.score
        self.pendiente, self.fase = None, CONSECUENCIA
        return r

    def continuar(self) -> bool:
        """Despues de las consecuencias: le toca al siguiente jugador o, si ya decidieron todos, se abre la
        siguiente publicacion (o termina la partida). False si no estaba en la fase de consecuencias."""
        if self.fase != CONSECUENCIA:
            return False
        self.turno += 1
        if self.turno < len(self.jugadores):
            self.fase = DECIDIENDO
            return True
        self.turno, self.indice = 0, self.indice + 1
        if self.indice < len(self.arboles):
            self.abrir_evento()
        else:
            self.fase = FIN
        return True

    def abrir_evento(self, indice: int | None = None) -> None:
        """Abre la publicacion `indice` (por defecto la actual) desde el primer turno. Si un jugador ya esta parado
        donde la noticia dejo evidencia, se revela sola."""
        if indice is not None:
            self.indice = indice
        self.turno, self.fase, self.pendiente = 0, DECIDIENDO, None
        evento = self.arbol.event
        for j in self.jugadores:
            j.investigacion = Investigacion(evento.clues, evidencias=evento.evidences)
            j.investigacion.revelar_evidencia(j.zona)

    # --- serializacion (para el servidor de sockets) ----------------------------------------
    def to_dict(self) -> dict:
        """Todo el estado en tipos de JSON. Las publicaciones y los mapas se guardan por id/ruta: son datos fijos
        de data/. shortcut: la animacion de una decision pendiente no se guarda; al restaurar pasa directo a las
        consecuencias (se guarda el impacto ya calculado)."""
        estado_rng = self.rng.getstate()
        p = self.pendiente
        return {
            "version": VERSION,
            "ciudad": self.ciudad.to_dict(),
            "jugadores": [{"id": j.id, "personaje": j.personaje.to_dict(), "zona": j.zona, "puntos": j.puntos,
                           "investigacion": j.investigacion.to_dict()} for j in self.jugadores],
            "eventos": [a.event.event_id for a in self.arboles],
            "indice": self.indice, "turno": self.turno, "fase": self.fase,
            "pendiente": None if p is None else {"jugador": p.jugador, "nodo": p.nodo.node_id,
                                                 "impacto": asdict(p.impacto), "aviso": p.aviso},
            "grafo": self.grafo.to_dict(),
            "rng": [estado_rng[0], list(estado_rng[1]), estado_rng[2]],
        }

    @classmethod
    def from_dict(cls, datos: dict, ruta_eventos=RUTA_EVENTOS, ruta_mapa=RUTA_GRAFO_CIUDAD) -> "PartidaSesion":
        if datos.get("version") != VERSION:
            raise ValueError(f"Version de sesion no soportada: {datos.get('version')}")
        por_id = {a.event.event_id: a for a in load_trees(ruta_eventos)}
        desconocidos = [i for i in datos["eventos"] if i not in por_id]
        if desconocidos:
            raise ValueError(f"Publicaciones desconocidas: {desconocidos}")
        arboles = [por_id[i] for i in datos["eventos"]]
        indice = int(datos["indice"])
        evento = arboles[min(indice, len(arboles) - 1)].event
        jugadores = [Jugador(d["id"], Personaje.from_dict(d["personaje"]), d["zona"], int(d["puntos"]),
                             Investigacion.from_dict(d["investigacion"], evento.clues, evento.evidences))
                     for d in datos["jugadores"]]
        rng = random.Random()
        s = datos["rng"]
        rng.setstate((s[0], tuple(s[1]), s[2]))
        sesion = cls(jugadores, arboles, GrafoSocial.from_dict(datos["grafo"]), GrafoCiudad.cargar(ruta_mapa), rng,
                     CityState.from_dict(datos["ciudad"]))
        sesion.indice, sesion.turno, sesion.fase = indice, int(datos["turno"]), datos["fase"]
        p = datos.get("pendiente")
        if p is not None:
            nodo = sesion.arbol.find(p["nodo"])
            if nodo is None:
                raise ValueError(f"Decision pendiente desconocida: {p['nodo']}")
            sesion.pendiente = ResultadoDecision(True, "", p["jugador"], nodo, Impact.from_dict(p["impacto"]),
                                                 p["aviso"])
        return sesion


def _validar_cantidad(n: int) -> None:
    if not MIN_JUGADORES <= n <= MAX_JUGADORES:
        raise ValueError(f"La partida es de {MIN_JUGADORES} a {MAX_JUGADORES} jugadores, no {n}")


def _clonar_vertice(grafo: GrafoSocial, nuevo: str) -> None:
    """Un jugador mas en la red: mismos contactos (entrantes y salientes, con los mismos pesos) que `jugador`."""
    base = grafo.vertice(JUGADOR)
    grafo.agregar_vertice(Ciudadano(nuevo, f"Jugador {nuevo[len(JUGADOR):]}", base.rol, base.pos))
    for a in grafo.aristas():       # aristas() es una copia: se puede agregar mientras se recorre
        if a.origen == JUGADOR:
            grafo.agregar_arista(nuevo, a.destino, a.peso, a.tipo)
        elif a.destino == JUGADOR:
            grafo.agregar_arista(a.origen, nuevo, a.peso, a.tipo)
