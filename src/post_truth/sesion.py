"""Sesion de partida: el estado y las reglas del juego, sin pygame ni vistas."""
from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass, field, replace
from typing import Sequence

from post_truth.config import DIAS_CAMPANA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role
from post_truth.models import credibilidad as cred
from post_truth.models import eleccion
from post_truth.models import fases
from post_truth.models import minijuego as mj
from post_truth.models import posts
from post_truth.models import roles
from post_truth.models import testigos as tg
from post_truth.models.personaje import Personaje
from post_truth.models.pistas import Evidencia, Investigacion, Pista
from post_truth.structures.arbol_dialogo import NodoDialogo
from post_truth.structures.grafo_ciudad import GrafoCiudad, Zona
from post_truth.structures.grafo_social import Ciudadano, GrafoSocial, TipoRelacion
from post_truth.structures.propagacion_vivo import ACTIVO, COMPARTIO, INMUNE, PropagacionEnVivo, ResultadoAccion
from post_truth.structures.propagacion import (REPORTAR, REPORTE_INFUNDADO, VERIFICAR, SimulacionDecision, es_falsa,
                                               fuerza_reportar, fuerza_verificar, mensaje_respaldo, reporte_rechazado,
                                               simular_decision)

DECIDIENDO, CONSECUENCIA, FIN = "decidiendo", "consecuencia", "fin"
FIN_DIA = "fin_dia"    # campana: el dia termino y se muestra su resumen
JUGADOR = "jugador"
MIN_JUGADORES, MAX_JUGADORES = 1, 4
VERSION = 1
PRESENTES = 3          # ciudadanos del grafo social en el lugar de la publicacion
UMBRAL_VIRAL = 300     # likes desde los que una publicacion es viral y se decide con reloj
TIEMPO_VIRAL = 25.0    # segundos por turno; corren tambien en la calle (buscar evidencia cuesta tiempo)
AVISO_VENCIDO = "Se te acabo el tiempo: la publicacion siguio circulando sin que nadie la frenara."
DIAS, NOTICIAS_POR_DIA = DIAS_CAMPANA, 2   # campana: cada dia trae sus noticias y una crisis viral
DURACION_DIA = 80.0                   # segundos de un dia (calle, decision y minijuegos): 4 dias = 5.3 min de reloj
MOMENTO_CRISIS = (0.2, 0.5)           # la crisis aparece entre el 20% y el 50% del dia (y su reloj cabe en el dia)
FACTOR_TIEMPO_EXTENDIDO = 1.5         # accesibilidad: dias y relojes mas largos
RITMO_TELEFONO = 0.25                 # con el telefono abierto el mundo corre al 25%...
RITMO_RUMOR_TELEFONO = 0.6            # ...pero el rumor al 60%, para que atajarlo sea un juego de reflejos
IMPACTO_EN_VIVO = 0.5                 # el rumor de cada crisis pesa la mitad: sin defender, la ciudad empeora sin hundirse
VIRAL_EN_VIVO = 0.35                  # fraccion de la red que cree el rumor para avisar que se volvio viral
CONCLUSION = {"buena": (2, 4), "a_ciegas": (1, 1), "error": (-4, -3), "no_concluyente": (0, 0)}   # (cred, puntos)
VEREDICTOS = ("falsa", "verdadera", "no_concluyente")
HERRAMIENTAS = {"verificador": "Verificador", "limitar": "Limitar cuenta", "desmentido": "Desmentido",
                "alertar": "Alertar prensa"}


@dataclass
class Campana:
    """Varios dias con reloj. Los indices apuntan a `PartidaSesion.arboles`: noticias del dia y una crisis viral
    por dia, que aparece a mitad de jornada e interrumpe la noticia en curso."""
    dias: list[list[int]]
    crisis: list[int]
    momento_crisis: list[float]       # fraccion del dia en que aparece cada crisis
    factor: float = 1.0               # FACTOR_TIEMPO_EXTENDIDO si se pidio tiempo extendido
    dia: int = 0
    t: float = 0.0                    # segundos transcurridos del dia
    cola: list[int] = field(default_factory=list)          # noticias del dia que faltan, en orden
    crisis_lanzada: bool = False
    resueltas: list[tuple[int, str]] = field(default_factory=list)   # (indice, accion) del dia, para el resumen
    ciudad_al_amanecer: dict = field(default_factory=dict)
    minijuegos_hoy: list[str] = field(default_factory=list)          # lugares cuyo minijuego ya se jugo hoy
    aliados_hoy: list[str] = field(default_factory=list)             # aliados que ya actuaron solos hoy

    @property
    def duracion(self) -> float:
        return DURACION_DIA * self.factor

    @property
    def fraccion(self) -> float:
        return min(1.0, self.t / self.duracion)

    @property
    def ultimo_dia(self) -> bool:
        return self.dia >= len(self.dias) - 1

    def to_dict(self) -> dict:
        return {"dias": self.dias, "crisis": self.crisis, "momento_crisis": self.momento_crisis, "factor": self.factor,
                "dia": self.dia, "t": self.t, "cola": self.cola, "crisis_lanzada": self.crisis_lanzada,
                "resueltas": [list(r) for r in self.resueltas], "ciudad_al_amanecer": self.ciudad_al_amanecer,
                "minijuegos_hoy": self.minijuegos_hoy, "aliados_hoy": self.aliados_hoy}

    @classmethod
    def from_dict(cls, d: dict) -> "Campana":
        return cls([list(x) for x in d["dias"]], list(d["crisis"]), list(d["momento_crisis"]), float(d["factor"]),
                   int(d["dia"]), float(d["t"]), list(d["cola"]), bool(d["crisis_lanzada"]),
                   [(int(i), a) for i, a in d["resueltas"]], dict(d["ciudad_al_amanecer"]),
                   list(d.get("minijuegos_hoy", [])), list(d.get("aliados_hoy", [])))


@dataclass
class Jugador:
    id: str
    personaje: Personaje
    zona: str
    puntos: int = 0
    investigacion: Investigacion = field(default_factory=lambda: Investigacion(()))
    credibilidad: int = cred.INICIAL
    historial: list[dict] = field(default_factory=list)   # {evento, accion, falsa, respaldo, credibilidad}
    posicion: tuple[float, float] | None = None           # donde esta en el mapa abierto (R8)
    en_zona: str | None = None                            # la zona bajo sus pies; None en la calle

    @property
    def falsas_compartidas(self) -> int:
        return sum(1 for h in self.historial if h["falsa"] and h["accion"] == "compartir")

    @property
    def rol(self):
        return self.personaje.rol


@dataclass(frozen=True)
class ResultadoInvestigar:
    ok: bool
    motivo: str = ""
    estado: str = ""
    pista: Pista | None = None


@dataclass(frozen=True)
class ResultadoConclusion:
    ok: bool
    motivo: str = ""
    como: str = ""             # buena | a_ciegas | error | no_concluyente
    calidad: int = 0
    credibilidad: int = 0
    puntos: int = 0


@dataclass(frozen=True)
class ResultadoViaje:
    ok: bool
    motivo: str = ""
    destino: str = ""
    ruta: tuple[str, ...] = ()
    evidencia: Evidencia | None = None
    revisada: bool = False


@dataclass(frozen=True)
class ResultadoDecision:
    ok: bool
    motivo: str = ""
    jugador: str = ""
    nodo: DecisionNode | None = None
    impacto: Impact = Impact()
    aviso: str = ""
    simulacion: SimulacionDecision | None = None
    vencido: bool = False   # la decidio el reloj, no el jugador
    alcance: float = 0.0    # fraccion de la red que recibio la publicacion (para la eleccion)
    respaldo: int = 0


class PartidaSesion:
    def __init__(self, jugadores: Sequence[Jugador], arboles: list[DecisionTree], grafo: GrafoSocial,
                 mapa: GrafoCiudad, rng: random.Random, ciudad: CityState | None = None) -> None:
        _validar_cantidad(len(jugadores))
        if not arboles:
            raise ValueError("La partida necesita al menos una publicacion")
        self.jugadores = list(jugadores)
        self.arboles = arboles
        self.grafo, self.mapa, self.rng = grafo, mapa, rng
        self.ciudad = ciudad if ciudad is not None else CityState()
        self.indice = 0
        self.turno = 0
        self.fase = DECIDIENDO
        self.pendiente: ResultadoDecision | None = None
        self.tiempo_restante: float | None = None   # None: la publicacion no es viral
        self.reloj_activo = False                   # arranca al ver la publicacion por primera vez
        self.campana: Campana | None = None         # None: partida clasica de publicaciones sueltas
        self.novedad = ""                           # "crisis" cuando aparece una; el controlador la avisa y la limpia
        self._en_pausa: dict[int, list[dict]] = {}  # investigacion de una noticia interrumpida por la crisis
        self._accion_aplicada = ""                  # la ultima decision aplicada (para el resumen del dia)
        self.minijuegos: dict[str, str] = {}        # lugar -> id del minijuego (data/minijuegos.json)
        self.minijuego: mj.Minijuego | None = None  # el que se esta jugando
        self.en_vivo: PropagacionEnVivo | None = None  # rumor corriendo en vivo por el grafo social (R2)
        self.en_vivo_viral = False                  # ya se aviso que el rumor en vivo se volvio viral
        self.notificaciones: list[dict] = []        # {"tipo", "titulo", "texto"} del telefono, la mas nueva al final
        self.leidas = 0                             # cuantas notificaciones ya se vieron
        self.post: dict | None = None               # post del jugador que esta corriendo: se cobra al apagarse
        self.enfriamiento_post = 0.0                # segundos para poder publicar otra vez
        self.asignacion: dict[str, str] = {}        # Role.name -> id del jugador humano o roles.ALIADO
        self.enfriamientos: dict[str, float] = {}   # "habilidad:<jugador>" o "aliado:<ROL>" -> segundos
        # --- estado del grafo de la ciudad en la campana (R9); el servidor sera autoritativo sobre esto ---
        self.fase_campana = -1                      # indice en data/fases.json (-1: aun no empieza)
        self.protestas: dict[str, int] = {}         # "a|b" -> distancia original de la arista que se cerro
        self.desinfo_zona: dict[str, int] = {}      # desinformacion acumulada por las noticias de cada zona
        self.zonas_crisis: list[str] = []
        self.aisladas: list[str] = []               # zonas sin camino a la Alcaldia
        self.sociales_cortadas: list[dict] = []     # aristas del grafo social cortadas por el aislamiento
        self.cambios_fase: list[tuple[str, str]] = []   # (tipo, texto) para la pantalla de la nueva fase
        self.anunciar_fase = False                  # empezo una fase: la pantalla de transicion la anuncia
        self.apoyo = {c: eleccion.APOYO_INICIAL for c in eleccion.CANDIDATOS}   # para la eleccion del alcalde
        self.por_rumores = {c: 0.0 for c in eleccion.CANDIDATOS}               # parte movida por publicaciones falsas

    @classmethod
    def nueva(cls, personajes: Sequence[Personaje], arboles: list[DecisionTree], grafo: GrafoSocial,
              mapa: GrafoCiudad, rng: random.Random) -> "PartidaSesion":
        _validar_cantidad(len(personajes))
        if len({p.rol for p in personajes}) != len(personajes):
            raise ValueError("Cada jugador necesita un rol distinto")
        jugadores = []
        for i, personaje in enumerate(personajes):
            id = JUGADOR if i == 0 else f"{JUGADOR}{i + 1}"
            if i:
                _clonar_vertice(grafo, id)
            grafo.cambiar_rol(id, personaje.rol)
            jugadores.append(Jugador(id, personaje, mapa.zona_inicial))
        sesion = cls(jugadores, arboles, grafo, mapa, rng)
        sesion.asignacion = _asignar_roles(jugadores)
        sesion.abrir_evento()
        return sesion

    @classmethod
    def nueva_campana(cls, personajes: Sequence[Personaje], todos: list[DecisionTree], grafo: GrafoSocial,
                      mapa: GrafoCiudad, rng: random.Random, dias: int = DIAS, por_dia: int = NOTICIAS_POR_DIA,
                      extendido: bool = False, minijuegos: dict[str, str] | None = None) -> "PartidaSesion":
        """Sortea las noticias del dia (no virales) y una crisis por dia (virales), sin repetir."""
        virales = [a for a in todos if a.event.likes >= UMBRAL_VIRAL]
        normales = [a for a in todos if a.event.likes < UMBRAL_VIRAL]
        if len(virales) < dias or len(normales) < dias * por_dia:
            raise ValueError("No hay suficientes publicaciones para la campana")
        elegidas = rng.sample(normales, dias * por_dia) + rng.sample(virales, dias)
        campana = Campana([list(range(d * por_dia, (d + 1) * por_dia)) for d in range(dias)],
                          [dias * por_dia + d for d in range(dias)],
                          [rng.uniform(*MOMENTO_CRISIS) for _ in range(dias)],
                          FACTOR_TIEMPO_EXTENDIDO if extendido else 1.0)
        sesion = cls.nueva(personajes, elegidas, grafo, mapa, rng)
        sesion.campana = campana
        sesion.minijuegos = dict(minijuegos or {})
        sesion._amanecer()
        return sesion

    @property
    def arbol(self) -> DecisionTree:
        return self.arboles[min(self.indice, len(self.arboles) - 1)]

    @property
    def jugador_actual(self) -> Jugador:
        return self.jugadores[(self.indice + self.turno) % len(self.jugadores)]

    @property
    def terminada(self) -> bool:
        return self.fase == FIN

    @property
    def presentes(self) -> list[Ciudadano]:
        """Quienes estan en el lugar con el jugador de turno: siempre los mismos para un lugar y una publicacion
        (se ordena por un hash estable, no por el rng, asi no cambia el azar de la partida)."""
        lugar, evento = self.jugador_actual.zona, self.arbol.event.event_id
        propios = {j.id for j in self.jugadores}

        def clave(c: Ciudadano) -> str:
            return hashlib.md5(f"{lugar}:{evento}:{c.id}".encode()).hexdigest()
        return sorted((c for c in self.grafo.vertices() if c.id not in propios), key=clave)[:PRESENTES]

    @property
    def es_viral(self) -> bool:
        return self.arbol.event.likes >= UMBRAL_VIRAL

    def _reiniciar_reloj(self) -> None:
        factor = self.campana.factor if self.campana else 1.0
        self.tiempo_restante = TIEMPO_VIRAL * factor if self.es_viral else None
        self.reloj_activo = False

    @property
    def tiempo_viral_total(self) -> float:
        return TIEMPO_VIRAL * (self.campana.factor if self.campana else 1.0)

    def iniciar_reloj(self) -> None:
        """El jugador de turno ya vio la publicacion: desde aqui corre su tiempo (si es viral)."""
        if self.tiempo_restante is not None and self.fase == DECIDIENDO:
            self.reloj_activo = True

    def transcurrir(self, dt: float) -> ResultadoDecision | None:
        """Descuenta `dt` del reloj del turno (y del dia, en campana). Al llegar a 0 decide sola (ver
        `decidir_por_tiempo`) y devuelve esa decision pendiente; si no, None. Solo corre mientras se decide."""
        if self.fase != DECIDIENDO or self.pendiente is not None:
            return None
        if self.campana is not None:
            ya_estaba = self.campana.crisis_lanzada
            if self._avanzar_dia(dt) or self.campana.crisis_lanzada != ya_estaba:
                return None   # se acabo el dia, o la crisis recien aparece: su reloj corre desde el proximo paso
            self._actualizar_ciudad()
            self._avanzar_en_vivo(dt / self.campana.factor)   # tiempo extendido: el rumor tambien va mas lento
            self.enfriamiento_post = max(0.0, self.enfriamiento_post - dt)
            for k in self.enfriamientos:
                self.enfriamientos[k] = max(0.0, self.enfriamientos[k] - dt)
        if not self.reloj_activo or self.tiempo_restante is None:
            return None
        self.tiempo_restante = max(0.0, self.tiempo_restante - dt)
        return self.decidir_por_tiempo() if self.tiempo_restante == 0 else None

    def decidir_por_tiempo(self) -> ResultadoDecision:
        """Nadie decidio a tiempo: cuenta como Ignorar y ademas nadie freno la publicacion."""
        j = self.jugador_actual
        ramas = self.arbol.root.children
        nodo = next((n for n in ramas if n.tipo == "ignorar"), ramas[0])
        r = self.decidir(j.id, nodo)
        castigo = Impact(misinformation=4, trust=-2) if es_falsa(self.arbol.event.truth_level) else Impact(trust=-2)
        self.pendiente = replace(r, impacto=r.impacto + castigo, aviso=AVISO_VENCIDO, vencido=True)
        self.reloj_activo = False
        return self.pendiente

    def jugador(self, id: str) -> Jugador:
        for j in self.jugadores:
            if j.id == id:
                return j
        raise KeyError(f"No existe el jugador: {id}")

    def _turno_de(self, id: str) -> tuple[Jugador, str]:
        """El jugador y, si no puede actuar ahora, el motivo."""
        j = self.jugador(id)
        if self.fase != DECIDIENDO:
            return j, "fuera_de_fase"
        if self.pendiente is not None:
            return j, "decision_pendiente"
        if j is not self.jugador_actual:
            return j, "no_es_su_turno"
        return j, ""

    def investigar(self, jugador: str, pista: Pista | str) -> ResultadoInvestigar:
        """Revisa una pista de la tarjeta."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoInvestigar(False, motivo)
        r = j.investigacion.investigar(pista.id if isinstance(pista, Pista) else pista)
        return ResultadoInvestigar(True, "", r.estado, r.pista)

    # --- ventana de investigacion: testigos y conclusion (R6) -----------------------------------------
    def testigos(self) -> list[tg.Testigo]:
        j = self.jugador_actual
        return tg.testigos(self.arbol.event.event_id, j.zona, self.presentes, j.investigacion.evidencias)

    def puede_hablar(self, t: tg.Testigo) -> bool:
        """A los de otra zona hay que ir a verlos primero (al llegar se revela su evidencia)."""
        return t.evidencia is None or self.jugador_actual.investigacion.esta_descubierta(t.evidencia.id)

    def interrogatorio(self, t: tg.Testigo) -> NodoDialogo:
        evidencias = self.jugador_actual.investigacion.evidencias
        lugar = evidencias[0].lugar if evidencias else "alcaldia"
        return tg.arbol(t, es_falsa(self.arbol.event.truth_level), lugar)

    def anotar_testimonio(self, jugador: str, t: tg.Testigo) -> None:
        """El testigo ya conto su version: queda en la investigacion (cuenta si es fiable)."""
        j, motivo = self._turno_de(jugador)
        if not motivo:
            j.investigacion.testimonios[t.id] = t.fiabilidad

    def concluir(self, jugador: str, veredicto: str) -> ResultadoConclusion:
        """Se evalua con la verdad de la noticia y la calidad de lo reunido. Una vez por noticia."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoConclusion(False, motivo)
        if veredicto not in VEREDICTOS:
            return ResultadoConclusion(False, "veredicto_desconocido")
        inv = j.investigacion
        if inv.conclusion is not None:
            return ResultadoConclusion(False, "ya_concluyo")
        falsa = es_falsa(self.arbol.event.truth_level)
        calidad = inv.calidad(falsa)
        inv.acierto = None if veredicto == "no_concluyente" else (veredicto == "falsa") == falsa
        inv.conclusion, inv.calidad_conclusion = veredicto, calidad
        como = inv.como_concluyo
        delta, puntos = CONCLUSION[como]
        j.credibilidad = cred.acotar(j.credibilidad + delta)
        j.puntos += puntos
        self.ciudad.apply(Impact(score=puntos))
        j.historial.append({"evento": f"conclusion:{self.arbol.event.event_id}", "accion": "concluir",
                            "falsa": falsa, "respaldo": 0, "credibilidad": delta})
        return ResultadoConclusion(True, "", como, calidad, delta, puntos)

    def viajar(self, jugador: str, zona: str) -> ResultadoViaje:
        """Ir a cualquier zona por el camino mas corto."""
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

    @property
    def zona_noticia(self) -> str:
        """Lugar donde ocurre la publicacion activa: la zona de su imagen."""
        imagen = self.arbol.event.image
        return imagen.motivo if imagen is not None else self.mapa.zona_inicial

    def situar(self, jugador: str, posicion: tuple[float, float], en_zona: str | None) -> None:
        """Posicion libre en el mapa y la zona que pisa; al pisar una zona, esa queda como su zona."""
        j = self.jugador(jugador)
        j.posicion, j.en_zona = (float(posicion[0]), float(posicion[1])), en_zona
        if en_zona is not None:
            self.llegar(jugador, en_zona)

    def llegar(self, jugador: str, zona: str) -> None:
        """El jugador del mundo llego a la plaza `zona`: la sesion queda en la misma zona."""
        if zona not in self.mapa:
            raise KeyError(f"Zona desconocida: {zona}")
        self.jugador(jugador).zona = zona

    def buscar_evidencia(self, jugador: str) -> Evidencia | None:
        """Revela la evidencia de la publicacion activa que hay en la zona del jugador."""
        j, motivo = self._turno_de(jugador)
        return None if motivo else j.investigacion.revelar_evidencia(j.zona)

    def decidir(self, jugador: str, accion: DecisionNode | str) -> ResultadoDecision:
        """Elige una rama de la publicacion."""
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoDecision(False, motivo, jugador)
        nodo = accion if isinstance(accion, DecisionNode) else self.arbol.find(accion)
        if nodo is None:
            raise KeyError(f"No existe la decision: {accion}")
        impacto = self.arbol.accumulated_impact(nodo.node_id).scaled_for_role(j.rol)
        respaldo = j.investigacion.respaldo(nodo.tipo) if nodo.tipo in (VERIFICAR, REPORTAR) else 2
        f = cred.factor(j.credibilidad)
        if nodo.tipo == VERIFICAR:
            impacto = impacto.atenuar_beneficios(min(1.0, fuerza_verificar(respaldo) * f))
        elif nodo.tipo == REPORTAR:
            impacto = impacto.atenuar_beneficios(min(1.0, fuerza_reportar(respaldo) * f))
            if reporte_rechazado(respaldo):
                impacto = impacto + REPORTE_INFUNDADO
        simulacion = self._simular(j, nodo, respaldo)
        if simulacion is not None:
            impacto = impacto + simulacion.resultado.impacto()
        res = simulacion.resultado if simulacion is not None else None
        alcance = res.alcanzados / max(1, res.poblacion - 1) if res is not None else 0.0
        self.pendiente = ResultadoDecision(True, "", j.id, nodo, impacto, mensaje_respaldo(nodo.tipo, respaldo),
                                           simulacion, alcance=alcance,
                                           respaldo=j.investigacion.respaldo(nodo.tipo or "verificar"))   # lo reunido de verdad
        return self.pendiente

    def _simular(self, j: Jugador, nodo: DecisionNode, respaldo: int) -> SimulacionDecision | None:
        if not nodo.tipo:
            return None
        propios = {x.id for x in self.jugadores}
        autor = self.rng.choice([c.id for c in self.grafo.vertices() if c.id not in propios])
        return simular_decision(self.grafo, nodo.tipo, es_falsa(self.arbol.event.truth_level), j.id, autor,
                                self.rng, respaldo=respaldo, credibilidad=cred.factor(j.credibilidad))

    def aplicar(self) -> ResultadoDecision:
        """Cierra la decision pendiente."""
        r = self.pendiente
        if r is None:
            raise ValueError("No hay una decision pendiente")
        self.ciudad.apply(r.impacto)
        self.jugador(r.jugador).puntos += r.impacto.score
        self._sumar_desinformacion(r.impacto.misinformation)
        self._accion_aplicada = "se acabo el tiempo" if r.vencido else r.nodo.label
        self._mover_apoyo(r)
        self._anotar(self.jugador(r.jugador), r)
        self.pendiente, self.fase = None, CONSECUENCIA
        return r

    def continuar(self) -> bool:
        """Despues de las consecuencias."""
        if self.fase != CONSECUENCIA:
            return False
        self.turno += 1
        if self.turno < len(self.jugadores):
            self.fase = DECIDIENDO
            self._reiniciar_reloj()
            return True
        if self.campana is not None:
            self.campana.resueltas.append((self.indice, self._accion_aplicada))
            self._siguiente_de_la_campana()
            return True
        self.turno, self.indice = 0, self.indice + 1
        if self.indice < len(self.arboles):
            self.abrir_evento()
        else:
            self.fase = FIN
        return True

    def abrir_evento(self, indice: int | None = None) -> None:
        """Abre la publicacion `indice` desde el primer turno."""
        if indice is not None:
            self.indice = indice
        self.turno, self.fase, self.pendiente = 0, DECIDIENDO, None
        self._reiniciar_reloj()
        evento = self.arbol.event
        for j in self.jugadores:
            j.investigacion = Investigacion(evento.clues, evidencias=evento.evidences)
            j.investigacion.revelar_evidencia(j.zona)

    def _mover_apoyo(self, r: ResultadoDecision) -> None:
        evento = self.arbol.event
        falsa = es_falsa(evento.truth_level)
        for candidato, sentido in evento.candidatos:
            delta = eleccion.efecto_en_apoyo(sentido, falsa, r.nodo.tipo, r.alcance, r.vencido)
            delta *= cred.factor(self.jugador(r.jugador).credibilidad)   # a un jugador creible se le cree mas
            nuevo = max(eleccion.APOYO_MINIMO, self.apoyo[candidato] + delta)
            if falsa:
                self.por_rumores[candidato] += nuevo - self.apoyo[candidato]
            self.apoyo[candidato] = nuevo

    def _anotar(self, j: Jugador, r: ResultadoDecision) -> None:
        """Historial y credibilidad del jugador que decidio."""
        falsa = es_falsa(self.arbol.event.truth_level)
        delta = cred.cambio(r.nodo.tipo, falsa, r.respaldo, r.vencido, j.falsas_compartidas, roles.costo_reporte(j.rol))
        j.credibilidad = cred.acotar(j.credibilidad + delta)
        j.historial.append({"evento": self.arbol.event.event_id, "accion": "vencido" if r.vencido else r.nodo.tipo,
                            "falsa": falsa, "respaldo": r.respaldo, "credibilidad": delta})

    # --- minijuegos -------------------------------------------------------------------------
    def minijuego_en(self, zona: str) -> str | None:
        """Id del minijuego disponible en `zona` para el jugador de turno (uno por lugar y por dia), o None."""
        if (self.campana is None or self.fase != DECIDIENDO or self.pendiente is not None
                or zona in self.campana.minijuegos_hoy):
            return None
        return self.minijuegos.get(zona)

    def iniciar_minijuego(self, zona: str) -> mj.Minijuego | None:
        id = self.minijuego_en(zona)
        if id is None:
            return None
        j = self.jugador_actual
        evidencias = len(j.investigacion.descubiertas) + sum(1 for h in j.historial if h.get("respaldo", 0) >= 1)
        contexto = mj.ContextoMinijuego(zona, j.id, j.rol.value, j.credibilidad, self.campana.dia,
                                        self.campana.factor > 1, evidencias, zona in self.zonas_crisis)
        self.minijuego = mj.crear(id, contexto)
        return self.minijuego

    def terminar_minijuego(self) -> mj.ResultadoMinijuego:
        """Aplica el resultado: impacto a la ciudad y puntos, credibilidad e historial al jugador."""
        m = self.minijuego
        if m is None:
            raise ValueError("No hay un minijuego en curso")
        r = m.resultado()
        j = self.jugador(m.contexto.jugador)
        self.ciudad.apply(r.impacto)
        j.puntos += r.impacto.score
        j.credibilidad = cred.acotar(j.credibilidad + r.credibilidad)
        j.historial.append({"evento": f"minijuego:{m.id}:{m.contexto.lugar}", "accion": "minijuego",
                            "falsa": False, "respaldo": 0, "credibilidad": r.credibilidad})
        self.campana.minijuegos_hoy.append(m.contexto.lugar)
        self.minijuego = None
        if r.rumor and self.en_vivo is None:
            self.iniciar_en_vivo()
            self.notificar("malo", "Arranca un rumor", f"Lo que quedo sin aclarar en {m.contexto.lugar.capitalize()} "
                                                       "ya corre por la red.")
        return r

    # --- propagacion en vivo -------------------------------------------------------------------
    def iniciar_en_vivo(self, autor: str | None = None, es_falsa: bool = True) -> PropagacionEnVivo:
        """Un rumor empieza a correr solo por el grafo social desde `autor` (al azar si no se dice)."""
        propios = {j.id for j in self.jugadores}
        if autor is None:
            autor = self.rng.choice([c.id for c in self.grafo.vertices() if c.id not in propios])
        j = self.jugador_actual
        self.en_vivo = PropagacionEnVivo(self.grafo, autor, j.id, j.credibilidad, self.rng.randrange(2 ** 31), es_falsa)
        self.en_vivo_viral = False
        return self.en_vivo

    def cerrar_en_vivo(self) -> Impact:
        """Lo que dejo el rumor entra a la ciudad y a los puntos de quien lo enfrento."""
        if self.en_vivo is None:
            raise ValueError("No hay un rumor en vivo")
        impacto = Impact(**{k: round(v * IMPACTO_EN_VIVO) for k, v in asdict(self.en_vivo.impacto()).items()})
        self.ciudad.apply(impacto)
        self.jugador(self.en_vivo.jugador).puntos += impacto.score
        self._sumar_desinformacion(impacto.misinformation)
        if self.post is not None:
            self._liquidar_post()
        self.en_vivo = None
        return impacto

    def avanzar_rumor(self, dt: float) -> None:
        """Solo el rumor en vivo (el telefono lo adelanta aparte del dia)."""
        if self.campana is not None and self.fase == DECIDIENDO and self.pendiente is None:
            self._avanzar_en_vivo(dt / self.campana.factor)

    def _avanzar_en_vivo(self, dt: float) -> None:
        v = self.en_vivo
        if v is None:
            return
        v.zonas_crisis = set(self.zonas_crisis)   # el rumor corre mas fuerte entre quienes viven en una zona en crisis
        v.avanzar(dt)
        if not self.en_vivo_viral and v.creen >= VIRAL_EN_VIVO * len(v.estado):
            self.en_vivo_viral = True
            self._aliados_reaccionan()
            self.novedad = self.novedad or "viral"   # no tapa el aviso de una crisis que aun no se ha visto
            self.notificar("malo" if v.es_falsa else "info", "Se volvio viral!",
                           f"{v.creen} personas ya creen " + ("el rumor. Frenalo desde la red." if v.es_falsa
                                                              else "la noticia."))
        if v.terminada:
            creen, total = v.creen, len(v.estado)
            self.cerrar_en_vivo()
            self.notificar("malo" if self.en_vivo_viral and v.es_falsa else "bueno",
                           "El rumor se apago" if v.es_falsa else "La noticia se apago",
                           f"Al final lo creyeron {creen} de {total} personas.")

    def publicar(self, post: posts.Post) -> tuple[bool, str, posts.Evaluacion | None]:
        """El jugador publica: si la red esta en calma su post arranca una propagacion en vivo; si ya corre una
        noticia, uno que dice lo mismo se suma a ella y uno veraz que la contradice sale como desmentido."""
        if self.enfriamiento_post > 0:
            return False, "enfriando", None
        if self.post is not None:
            return False, "en_curso", None
        j = self.jugador_actual
        reglas = posts.reglas()
        ev = reglas.evaluar(post, j.rol.name)
        v = self.en_vivo
        if v is None:
            semilla = int(hashlib.md5(f"{post.to_dict()}:{self.campana.dia if self.campana else 0}:"
                                      f"{len(self.notificaciones)}".encode()).hexdigest()[:8], 16)
            self.en_vivo = PropagacionEnVivo(self.grafo, j.id, j.id, j.credibilidad, semilla, ev.es_falsa,
                                             ev.alcance * (0.5 if ev.desmiente else 1.0))   # desmentir la nada no interesa
            self.en_vivo_viral = False
        elif ev.es_falsa == v.es_falsa:
            v.estado[j.id], v.rumor[j.id] = COMPARTIO, ACTIVO
        elif not ev.es_falsa:
            v.estado[j.id], v.desmentido[j.id] = INMUNE, ACTIVO
        else:
            return False, "contradice_verdad", ev
        self.post = {"post": post.to_dict(), "jugador": j.id}
        self.enfriamiento_post = reglas.reglas["enfriamiento"]
        titular = next(t["texto"] for t in reglas.opciones("titular", j.rol.name) if t["id"] == post.titular)
        self.notificar("info", "Publicaste", titular)
        return True, "", ev

    def _liquidar_post(self) -> None:
        """Se apago la noticia: el post deja sus conflictos y convivencia y se cobra (o premia) la credibilidad."""
        v, datos = self.en_vivo, self.post
        self.post = None
        post, j = posts.Post(**datos["post"]), self.jugador(datos["jugador"])
        reglas = posts.reglas()
        ev = reglas.evaluar(post, j.rol.name)
        llego = 1 - v.contar("sin_enterarse") / len(v.estado)
        self.ciudad.apply(Impact(conflicts=reglas.conflictos(ev, llego), coexistence=ev.convivencia))
        delta = reglas.credibilidad(post, ev, self.en_vivo_viral)
        j.credibilidad = cred.acotar(j.credibilidad + delta)
        j.historial.append({"evento": f"post:{post.titular}", "accion": "publicar", "falsa": ev.es_falsa,
                            "respaldo": 0, "credibilidad": delta})
        self.notificar("bueno" if delta >= 0 else "malo", f"Tu publicacion: credibilidad {delta:+}",
                       "Sin fuente, agresiva o falsa cuesta; veraz y verificable suma.")

    # --- roles: habilidades y aliados (R7) ------------------------------------------------------
    def aliados(self) -> list[Role]:
        """Los roles que juega la computadora, en el orden de Role."""
        return [r for r in Role if self.asignacion.get(r.name) == roles.ALIADO]

    def asignar(self, rol: Role, jugador: str | None) -> None:
        """Un rol pasa a un humano (su id) o, con None, a un aliado (el multijugador reemplaza aliados)."""
        if jugador is not None:
            self.jugador(jugador)   # valida que exista
        self.asignacion[rol.name] = jugador or roles.ALIADO

    def falta(self, clave: str) -> float:
        return self.enfriamientos.get(clave, 0.0)

    def nodo_aliado(self, rol: Role) -> str | None:
        """El ciudadano del grafo social que hace de aliado: el primero de ese rol que no es un jugador."""
        propios = {j.id for j in self.jugadores}
        return next((c.id for c in sorted(self.grafo.vertices(), key=lambda c: c.id)
                     if c.rol is rol and c.id not in propios), None)

    def usar_habilidad(self, jugador: str) -> ResultadoAccion:
        j, motivo = self._turno_de(jugador)
        if motivo:
            return ResultadoAccion(False, motivo)
        clave = f"habilidad:{j.id}"
        if self.falta(clave) > 0:
            return ResultadoAccion(False, "enfriando")
        v = self.en_vivo
        if j.rol is Role.JOURNALIST:
            r = self._revelar_a_distancia(j)
        elif j.rol is Role.INFLUENCER:
            if v is None:
                return ResultadoAccion(False, "sin_rumor")
            v.estado[j.id], v.desmentido[j.id] = INMUNE, ACTIVO
            v.fuerza_desmentido *= roles.DESMENTIDO_VIRAL
            r = ResultadoAccion(True)
        else:
            self.ciudad.apply(roles.COMUNICADO if j.rol is Role.CANDIDATE else roles.CONVIVENCIA)
            r = ResultadoAccion(True)
        if r.ok:
            h = roles.HABILIDADES[j.rol]
            self.enfriamientos[clave] = h.enfriamiento
            self.notificar("bueno", h.nombre, h.descripcion)
        return r

    def _revelar_a_distancia(self, j: Jugador) -> ResultadoAccion:
        pendientes = j.investigacion.lugares_pendientes()
        if not pendientes:
            return ResultadoAccion(False, "nada_pendiente")
        costos = self.mapa.costos_desde(j.zona)   # Dijkstra: la mas cercana
        j.investigacion.revelar_evidencia(min(pendientes, key=lambda z: (costos.get(z, float("inf")), z)))
        return ResultadoAccion(True)

    def pedir_ayuda(self, rol: Role) -> ResultadoAccion:
        """Politica sencilla de cada aliado; con enfriamiento por aliado."""
        if self.asignacion.get(rol.name) != roles.ALIADO:
            return ResultadoAccion(False, "no_es_aliado")
        clave = f"aliado:{rol.name}"
        if self.falta(clave) > 0:
            return ResultadoAccion(False, "enfriando")
        v, j = self.en_vivo, self.jugador_actual
        if rol is Role.JOURNALIST:      # verifica la noticia pendiente: revela una senal (las que dicen algo primero)
            inv = j.investigacion
            pendientes = sorted((p for p in inv.pistas if not inv.esta_descubierta(p.id)),
                                key=lambda p: p.senal.value == "neutra")
            if not pendientes:
                return ResultadoAccion(False, "nada_pendiente")
            inv.investigar(pendientes[0].id)
        elif rol is Role.INFLUENCER:    # difunde tu desmentido desde su cuenta
            nodo = self.nodo_aliado(rol)
            if v is None:
                return ResultadoAccion(False, "sin_rumor")
            if not v.desmentido or nodo is None:
                return ResultadoAccion(False, "sin_desmentido")
            v.estado[nodo], v.desmentido[nodo] = INMUNE, ACTIVO
        elif rol is Role.CANDIDATE:
            self.ciudad.apply(roles.COMUNICADO_ALIADO)
        elif v is not None:             # Ciudadano: reporta la cuenta que solto el rumor
            v.limitar(v.autor)
        else:
            self.ciudad.apply(roles.CONVIVENCIA_ALIADO)
        self.enfriamientos[clave] = roles.ENFRIAMIENTO_ALIADO
        self.notificar("bueno", f"{rol.value} aliado", roles.AYUDAS[rol])
        return ResultadoAccion(True)

    def _aliados_reaccionan(self) -> None:
        """Cuando un rumor se vuelve viral, cada aliado actua solo una vez por dia (si esta listo)."""
        if self.campana is None:
            return
        for rol in self.aliados():
            if rol.name not in self.campana.aliados_hoy and self.pedir_ayuda(rol).ok:
                self.campana.aliados_hoy.append(rol.name)

    def notificar(self, tipo: str, titulo: str, texto: str) -> None:
        self.notificaciones.append({"tipo": tipo, "titulo": titulo, "texto": texto})

    @property
    def sin_leer(self) -> int:
        return len(self.notificaciones) - self.leidas

    def usar_herramienta(self, accion: str, ciudadano: str | None = None) -> ResultadoAccion:
        """Las herramientas del telefono sobre el rumor en vivo: verificador, limitar, desmentido o alertar."""
        v = self.en_vivo
        if v is None:
            return ResultadoAccion(False, "sin_rumor")
        r = {"verificador": lambda: v.poner_verificador(ciudadano), "limitar": lambda: v.limitar_cuenta(ciudadano),
             "desmentido": v.lanzar_desmentido, "alertar": v.alertar_periodistas}[accion]()
        if r.ok:
            sobre = f" sobre {self.grafo.vertice(ciudadano).nombre}" if accion in ("verificador", "limitar") else ""
            self.notificar("bueno", HERRAMIENTAS[accion], f"Usaste {HERRAMIENTAS[accion].lower()}{sobre}.")
        return r

    def resultado_eleccion(self) -> eleccion.ResultadoEleccion:
        return eleccion.calcular(self.apoyo, self.por_rumores, self.ciudad)

    # --- campana ---------------------------------------------------------------------------
    def _amanecer(self) -> None:
        c = self.campana
        c.t, c.crisis_lanzada, c.resueltas, c.minijuegos_hoy, c.aliados_hoy = 0.0, False, [], [], []
        c.cola = list(c.dias[c.dia][1:])
        c.ciudad_al_amanecer = self.ciudad.to_dict()
        self._en_pausa.clear()
        self._entrar_fase()
        self.abrir_evento(c.dias[c.dia][0])

    # --- fases que cambian el grafo de la ciudad (R9) ----------------------------------------------
    @property
    def fase_actual(self) -> fases.Fase | None:
        return fases.reglas().fases[self.fase_campana] if self.fase_campana >= 0 else None

    def _entrar_fase(self) -> None:
        """Si el dia empieza una fase nueva, inserta sus zonas (vertice + aristas) y anota lo que cambio."""
        reglas = fases.reglas()
        i = reglas.indice_del_dia(self.campana.dia)
        if i == self.fase_campana:
            return
        self.anunciar_fase = self.fase_campana >= 0   # la primera fase la anuncia el dia, no una pantalla
        self.fase_campana = i
        cambios: list[tuple[str, str]] = []
        for id in reglas.fases[i].abre:
            if id not in self.mapa:
                self._abrir_zona(id, reglas.zonas_nuevas[id])
                cambios.append(("bueno", f"Se abrio {reglas.zonas_nuevas[id]['nombre']}: termino la obra."))
        antes = (set(self.protestas), set(self.aisladas), set(self.zonas_crisis))
        cambios += self._actualizar_ciudad()
        nombre = lambda z: self.mapa.zona(z).nombre if z in self.mapa else z  # noqa: E731
        sigue = ([("malo", f"Sigue la protesta en {' - '.join(nombre(z) for z in c.split('|'))}.")
                  for c in antes[0] & set(self.protestas)]                  # lo que ya estaba mal y sigue igual
                 + [("malo", f"{nombre(z)} sigue aislada.") for z in antes[1] & set(self.aisladas)]
                 + [("malo", f"{nombre(z)} sigue en crisis.") for z in antes[2] & set(self.zonas_crisis)])
        self.cambios_fase = cambios + sorted(sigue)

    def _abrir_zona(self, id: str, datos: dict) -> None:
        """Insertar el vertice es O(1) y cada arista O(1): en total O(grado de la zona nueva)."""
        self.mapa.agregar_zona(Zona(id, datos["nombre"], tuple(datos["pos"])))
        for vecino, distancia in datos["conexiones"].items():
            if vecino in self.mapa:
                self.mapa.agregar_conexion(id, vecino, distancia)

    def _sumar_desinformacion(self, cantidad: int) -> None:
        """La desinformacion de una noticia se queda en su zona (la del lugar de la publicacion)."""
        if self.campana is not None and cantidad:
            z = self.zona_noticia
            self.desinfo_zona[z] = max(0, self.desinfo_zona.get(z, 0) + cantidad)

    def _actualizar_ciudad(self) -> list[tuple[str, str]]:
        """Protestas, zonas en crisis y conectividad. Devuelve (y notifica) lo que cambio."""
        reglas = fases.reglas()
        cambios: list[tuple[str, str]] = []
        grafo_cambio = False
        for p in reglas.protestas:   # eliminar o restaurar una arista: O(1) cada una
            valor = getattr(self.ciudad, p.indicador)
            nombre = f"{self.mapa.zona(p.a).nombre}-{self.mapa.zona(p.b).nombre}" if p.a in self.mapa and p.b in self.mapa else ""
            if p.clave not in self.protestas and valor > p.cierra and nombre and self.mapa.distancia(p.a, p.b):
                self.protestas[p.clave] = self.mapa.distancia(p.a, p.b)
                self.mapa.eliminar_conexion(p.a, p.b)
                cambios.append(("malo", f"Protesta: se cerro la calle {nombre}."))
                grafo_cambio = True
            elif p.clave in self.protestas and valor < p.reabre and nombre:
                self.mapa.agregar_conexion(p.a, p.b, self.protestas.pop(p.clave))
                cambios.append(("bueno", f"Termino la protesta: se reabrio la calle {nombre}."))
                grafo_cambio = True
        for z in [z.id for z in self.mapa.zonas()]:   # crisis por zona, con histeresis
            d = self.desinfo_zona.get(z, 0)
            if z not in self.zonas_crisis and d >= reglas.crisis_entra:
                self.zonas_crisis.append(z)
                cambios.append(("malo", f"Zona en crisis: {self.mapa.zona(z).nombre}. Los rumores corren mas rapido."))
            elif z in self.zonas_crisis and d < reglas.crisis_sale:
                self.zonas_crisis.remove(z)
                cambios.append(("bueno", f"{self.mapa.zona(z).nombre} salio de la crisis."))
        aisladas = self._aisladas(reglas.centro)
        if grafo_cambio or aisladas != self.aisladas or not self.aisladas and self.sociales_cortadas:
            for z in sorted(set(aisladas) - set(self.aisladas)):
                cambios.append(("malo", f"{self.mapa.zona(z).nombre} quedo aislada: no le llegan los desmentidos."))
            for z in sorted(set(self.aisladas) - set(aisladas)):
                if z in self.mapa:
                    cambios.append(("bueno", f"{self.mapa.zona(z).nombre} volvio a estar conectada."))
            self.aisladas = aisladas
            self._aislar_grafo_social()
        for tipo, texto in cambios:
            self.notificar(tipo, "La ciudad cambia", texto)
        if cambios and self.fase == DECIDIENDO:
            self.novedad = self.novedad or "mapa"
        return cambios

    def _aisladas(self, centro: str) -> list[str]:
        """BFS desde la Alcaldia, O(V+E): toda zona que no alcanza queda aislada. BFS (y no DFS ni Dijkstra) porque
        solo importa SI hay camino, no cual ni cuanto cuesta, y lo da en tiempo lineal."""
        alcanzadas = self.mapa.saltos(centro) if centro in self.mapa else {}
        return sorted(z.id for z in self.mapa.zonas() if z.id not in alcanzadas)

    def _aislar_grafo_social(self) -> None:
        """El grafo de la ciudad afecta al social: se restauran las aristas cortadas antes y se cortan las que entran
        desde fuera a quien vive en una zona aislada (asi no le llegan los desmentidos). O(E social)."""
        for a in self.sociales_cortadas:
            if self.grafo.arista(a["origen"], a["destino"]) is None:
                self.grafo.agregar_arista(a["origen"], a["destino"], a["peso"], TipoRelacion(a["tipo"]))
        self.sociales_cortadas = []
        aisladas = set(self.aisladas)
        for a in self.grafo.aristas():
            zona = self.grafo.vertice(a.destino).zona
            if zona in aisladas and self.grafo.vertice(a.origen).zona != zona:
                self.sociales_cortadas.append(a.to_dict())
                self.grafo.eliminar_arista(a.origen, a.destino)

    def empezar_siguiente_dia(self) -> bool:
        """Despues del resumen del dia. False (y fase FIN: elegir alcalde) si ya fue el ultimo."""
        if self.fase != FIN_DIA:
            return False
        if self.campana.ultimo_dia:
            self.fase = FIN
            return False
        self.campana.dia += 1
        self._amanecer()
        return True

    def _lanzar_crisis(self) -> None:
        """La crisis del dia pasa al frente; la noticia en curso (con lo investigado) espera su turno."""
        c = self.campana
        if self.fase == DECIDIENDO and self.indice not in c.crisis:
            c.cola.insert(0, self.indice)
            self._en_pausa[self.indice] = [j.investigacion.to_dict() for j in self.jugadores]
        c.crisis_lanzada = True
        self.abrir_evento(c.crisis[c.dia])
        self.reloj_activo = self.tiempo_restante is not None   # la crisis no espera a que la vean
        self.novedad = "crisis"
        self.notificar("crisis", "Crisis viral!", f"Algo se esta regando en {self.zona_noticia.capitalize()}.")
        if self.en_vivo is None:   # el rumor de la crisis corre solo por la red (semilla por hash: no toca el rng)
            semilla = int(hashlib.md5(f"{self.arbol.event.event_id}:{c.dia}".encode()).hexdigest()[:8], 16)
            propios = {j.id for j in self.jugadores}
            autores = sorted(v.id for v in self.grafo.vertices() if v.id not in propios)
            j = self.jugador_actual
            self.en_vivo = PropagacionEnVivo(self.grafo, autores[semilla % len(autores)], j.id, j.credibilidad,
                                             semilla, es_falsa(self.arbol.event.truth_level))
            self.en_vivo_viral = False

    def _siguiente_de_la_campana(self) -> None:
        c = self.campana
        if c.cola:
            siguiente = c.cola.pop(0)
            self.abrir_evento(siguiente)
            guardadas = self._en_pausa.pop(siguiente, None)
            if guardadas is not None:
                evento = self.arbol.event
                for j, datos in zip(self.jugadores, guardadas):
                    j.investigacion = Investigacion.from_dict(datos, evento.clues, evento.evidences)
        elif not c.crisis_lanzada:      # se resolvio todo antes de tiempo: la crisis no se salta
            self._lanzar_crisis()
        else:
            self.fase = FIN_DIA

    def _avanzar_dia(self, dt: float) -> bool:
        """True si el dia termino (por tiempo) en este paso."""
        c = self.campana
        c.t += dt
        if not c.crisis_lanzada and c.t >= c.momento_crisis[c.dia] * c.duracion:
            self._lanzar_crisis()
        if c.t < c.duracion:
            return False
        self._cerrar_dia_sin_respuesta()
        return True

    def _cerrar_dia_sin_respuesta(self) -> None:
        """Se acabo el dia: lo que quedo pendiente cuenta como Ignorar (sin castigo extra) y sale el resumen."""
        c = self.campana
        for indice in [self.indice] + c.cola + ([] if c.crisis_lanzada else [c.crisis[c.dia]]):
            self.indice, self.turno, self.fase, self.pendiente = indice, 0, DECIDIENDO, None
            nodo = next((n for n in self.arbol.root.children if n.tipo == "ignorar"), None)
            if nodo is not None:
                self.decidir(self.jugador_actual.id, nodo)
                self.aplicar()
            c.resueltas.append((indice, "sin respuesta"))
        c.cola, c.crisis_lanzada = [], True
        self.pendiente, self.reloj_activo, self.fase = None, False, FIN_DIA
        if self.en_vivo is not None:   # el rumor que quedaba corriendo deja su huella en la ciudad
            self.cerrar_en_vivo()

    def to_dict(self) -> dict:
        """Todo el estado en tipos de JSON."""
        estado_rng = self.rng.getstate()
        p = self.pendiente
        return {
            "version": VERSION,
            "ciudad": self.ciudad.to_dict(),
            "jugadores": [{"id": j.id, "personaje": j.personaje.to_dict(), "zona": j.zona, "puntos": j.puntos,
                           "investigacion": j.investigacion.to_dict(), "credibilidad": j.credibilidad,
                           "historial": j.historial, "posicion": j.posicion, "en_zona": j.en_zona}
                          for j in self.jugadores],
            "eventos": [a.event.event_id for a in self.arboles],
            "indice": self.indice, "turno": self.turno, "fase": self.fase,
            "pendiente": None if p is None else {"jugador": p.jugador, "nodo": p.nodo.node_id,
                                                 "impacto": asdict(p.impacto), "aviso": p.aviso,
                                                 "vencido": p.vencido, "alcance": p.alcance,
                                                 "respaldo": p.respaldo},
            "reloj": {"restante": self.tiempo_restante, "activo": self.reloj_activo},
            "campana": None if self.campana is None else self.campana.to_dict(),
            "apoyo": self.apoyo, "por_rumores": self.por_rumores,
            "minijuegos": self.minijuegos,
            "minijuego": None if self.minijuego is None else self.minijuego.to_dict(),
            "en_vivo": None if self.en_vivo is None else self.en_vivo.to_dict(),
            "en_vivo_viral": self.en_vivo_viral, "notificaciones": self.notificaciones, "leidas": self.leidas,
            "post": self.post, "enfriamiento_post": self.enfriamiento_post,
            "asignacion": self.asignacion, "enfriamientos": self.enfriamientos,
            "mapa": self.mapa.to_dict(), "fase_campana": self.fase_campana, "protestas": self.protestas,
            "desinfo_zona": self.desinfo_zona, "zonas_crisis": self.zonas_crisis, "aisladas": self.aisladas,
            "sociales_cortadas": self.sociales_cortadas, "cambios_fase": self.cambios_fase,
            "anunciar_fase": self.anunciar_fase,
            "en_pausa": {str(k): v for k, v in self._en_pausa.items()},
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
                             Investigacion.from_dict(d["investigacion"], evento.clues, evento.evidences),
                             int(d.get("credibilidad", cred.INICIAL)), list(d.get("historial", [])),
                             tuple(d["posicion"]) if d.get("posicion") else None, d.get("en_zona"))
                     for d in datos["jugadores"]]
        rng = random.Random()
        s = datos["rng"]
        rng.setstate((s[0], tuple(s[1]), s[2]))
        sesion = cls(jugadores, arboles, GrafoSocial.from_dict(datos["grafo"]),
                     GrafoCiudad.from_dict(datos["mapa"]) if "mapa" in datos else GrafoCiudad.cargar(ruta_mapa), rng,
                     CityState.from_dict(datos["ciudad"]))
        sesion.indice, sesion.turno, sesion.fase = indice, int(datos["turno"]), datos["fase"]
        sesion.apoyo.update(datos.get("apoyo", {}))
        sesion.minijuegos = dict(datos.get("minijuegos", {}))
        if datos.get("minijuego") is not None:
            sesion.minijuego = mj.desde_dict(datos["minijuego"])
        if datos.get("en_vivo") is not None:
            sesion.en_vivo = PropagacionEnVivo.from_dict(datos["en_vivo"], sesion.grafo)
        sesion.en_vivo_viral = bool(datos.get("en_vivo_viral", False))
        sesion.notificaciones = [dict(n) for n in datos.get("notificaciones", [])]
        sesion.leidas = int(datos.get("leidas", 0))
        sesion.post = datos.get("post")
        sesion.enfriamiento_post = float(datos.get("enfriamiento_post", 0.0))
        sesion.asignacion = dict(datos.get("asignacion") or _asignar_roles(sesion.jugadores))
        sesion.enfriamientos = {k: float(v) for k, v in datos.get("enfriamientos", {}).items()}
        sesion.fase_campana = int(datos.get("fase_campana", -1))
        sesion.protestas = {k: int(v) for k, v in datos.get("protestas", {}).items()}
        sesion.desinfo_zona = {k: int(v) for k, v in datos.get("desinfo_zona", {}).items()}
        sesion.zonas_crisis, sesion.aisladas = list(datos.get("zonas_crisis", [])), list(datos.get("aisladas", []))
        sesion.sociales_cortadas = [dict(a) for a in datos.get("sociales_cortadas", [])]
        sesion.cambios_fase = [tuple(c) for c in datos.get("cambios_fase", [])]
        sesion.anunciar_fase = bool(datos.get("anunciar_fase", False))
        sesion.por_rumores.update(datos.get("por_rumores", {}))
        if datos.get("campana") is not None:
            sesion.campana = Campana.from_dict(datos["campana"])
            sesion._en_pausa = {int(k): v for k, v in datos.get("en_pausa", {}).items()}
        reloj = datos.get("reloj", {})
        sesion.tiempo_restante, sesion.reloj_activo = reloj.get("restante"), bool(reloj.get("activo", False))
        p = datos.get("pendiente")
        if p is not None:
            nodo = sesion.arbol.find(p["nodo"])
            if nodo is None:
                raise ValueError(f"Decision pendiente desconocida: {p['nodo']}")
            sesion.pendiente = ResultadoDecision(True, "", p["jugador"], nodo, Impact.from_dict(p["impacto"]),
                                                 p["aviso"], vencido=bool(p.get("vencido", False)),
                                                 alcance=float(p.get("alcance", 0.0)),
                                                 respaldo=int(p.get("respaldo", 0)))
        return sesion


def _asignar_roles(jugadores: Sequence[Jugador]) -> dict[str, str]:
    """Cada rol elegido queda con su jugador (el primero que lo eligio); los demas, con un aliado."""
    asignacion = {r.name: roles.ALIADO for r in Role}
    for j in reversed(jugadores):
        asignacion[j.rol.name] = j.id
    return asignacion


def _validar_cantidad(n: int) -> None:
    if not MIN_JUGADORES <= n <= MAX_JUGADORES:
        raise ValueError(f"La partida es de {MIN_JUGADORES} a {MAX_JUGADORES} jugadores, no {n}")


def _clonar_vertice(grafo: GrafoSocial, nuevo: str) -> None:
    """Un jugador mas en la red: mismos contactos que `jugador`."""
    base = grafo.vertice(JUGADOR)
    grafo.agregar_vertice(Ciudadano(nuevo, f"Jugador {nuevo[len(JUGADOR):]}", base.rol, base.pos))
    for a in grafo.aristas():
        if a.origen == JUGADOR:
            grafo.agregar_arista(nuevo, a.destino, a.peso, a.tipo)
        elif a.destino == JUGADOR:
            grafo.agregar_arista(a.origen, nuevo, a.peso, a.tipo)
