"""Sesion de partida: el estado y las reglas del juego, sin pygame ni vistas."""
from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass, field, replace
from typing import Sequence

from post_truth.config import DIAS_CAMPANA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD
from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact
from post_truth.models import credibilidad as cred
from post_truth.models import eleccion
from post_truth.models.personaje import Personaje
from post_truth.models.pistas import Evidencia, Investigacion, Pista
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import Ciudadano, GrafoSocial
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
TIEMPO_VIRAL = 30.0    # segundos por turno; corren tambien en la calle (buscar evidencia cuesta tiempo)
AVISO_VENCIDO = "Se te acabo el tiempo: la publicacion siguio circulando sin que nadie la frenara."
DIAS, NOTICIAS_POR_DIA = DIAS_CAMPANA, 2   # campana: cada dia trae sus noticias y una crisis viral
DURACION_DIA = 150.0                  # segundos de un dia (corre en la calle y mientras se decide)
MOMENTO_CRISIS = (0.3, 0.7)           # la crisis aparece entre el 30% y el 70% del dia
FACTOR_TIEMPO_EXTENDIDO = 1.5         # accesibilidad: dias y relojes mas largos


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
                "resueltas": [list(r) for r in self.resueltas], "ciudad_al_amanecer": self.ciudad_al_amanecer}

    @classmethod
    def from_dict(cls, d: dict) -> "Campana":
        return cls([list(x) for x in d["dias"]], list(d["crisis"]), list(d["momento_crisis"]), float(d["factor"]),
                   int(d["dia"]), float(d["t"]), list(d["cola"]), bool(d["crisis_lanzada"]),
                   [(int(i), a) for i, a in d["resueltas"]], dict(d["ciudad_al_amanecer"]))


@dataclass
class Jugador:
    id: str
    personaje: Personaje
    zona: str
    puntos: int = 0
    investigacion: Investigacion = field(default_factory=lambda: Investigacion(()))
    credibilidad: int = cred.INICIAL
    historial: list[dict] = field(default_factory=list)   # {evento, accion, falsa, respaldo, credibilidad}

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
        self.apoyo = {c: eleccion.APOYO_INICIAL for c in eleccion.CANDIDATOS}   # para la eleccion del alcalde
        self.por_rumores = {c: 0.0 for c in eleccion.CANDIDATOS}               # parte movida por publicaciones falsas

    @classmethod
    def nueva(cls, personajes: Sequence[Personaje], arboles: list[DecisionTree], grafo: GrafoSocial,
              mapa: GrafoCiudad, rng: random.Random) -> "PartidaSesion":
        _validar_cantidad(len(personajes))
        jugadores = []
        for i, personaje in enumerate(personajes):
            id = JUGADOR if i == 0 else f"{JUGADOR}{i + 1}"
            if i:
                _clonar_vertice(grafo, id)
            grafo.cambiar_rol(id, personaje.rol)
            jugadores.append(Jugador(id, personaje, mapa.zona_inicial))
        sesion = cls(jugadores, arboles, grafo, mapa, rng)
        sesion.abrir_evento()
        return sesion

    @classmethod
    def nueva_campana(cls, personajes: Sequence[Personaje], todos: list[DecisionTree], grafo: GrafoSocial,
                      mapa: GrafoCiudad, rng: random.Random, dias: int = DIAS, por_dia: int = NOTICIAS_POR_DIA,
                      extendido: bool = False) -> "PartidaSesion":
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
        if self.campana is not None and self._avanzar_dia(dt):
            return None
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
        delta = cred.cambio(r.nodo.tipo, falsa, r.respaldo, r.vencido, j.falsas_compartidas)
        j.credibilidad = cred.acotar(j.credibilidad + delta)
        j.historial.append({"evento": self.arbol.event.event_id, "accion": "vencido" if r.vencido else r.nodo.tipo,
                            "falsa": falsa, "respaldo": r.respaldo, "credibilidad": delta})

    def resultado_eleccion(self) -> eleccion.ResultadoEleccion:
        return eleccion.calcular(self.apoyo, self.por_rumores, self.ciudad)

    # --- campana ---------------------------------------------------------------------------
    def _amanecer(self) -> None:
        c = self.campana
        c.t, c.crisis_lanzada, c.resueltas = 0.0, False, []
        c.cola = list(c.dias[c.dia][1:])
        c.ciudad_al_amanecer = self.ciudad.to_dict()
        self._en_pausa.clear()
        self.abrir_evento(c.dias[c.dia][0])

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

    def to_dict(self) -> dict:
        """Todo el estado en tipos de JSON."""
        estado_rng = self.rng.getstate()
        p = self.pendiente
        return {
            "version": VERSION,
            "ciudad": self.ciudad.to_dict(),
            "jugadores": [{"id": j.id, "personaje": j.personaje.to_dict(), "zona": j.zona, "puntos": j.puntos,
                           "investigacion": j.investigacion.to_dict(), "credibilidad": j.credibilidad,
                           "historial": j.historial} for j in self.jugadores],
            "eventos": [a.event.event_id for a in self.arboles],
            "indice": self.indice, "turno": self.turno, "fase": self.fase,
            "pendiente": None if p is None else {"jugador": p.jugador, "nodo": p.nodo.node_id,
                                                 "impacto": asdict(p.impacto), "aviso": p.aviso,
                                                 "vencido": p.vencido, "alcance": p.alcance,
                                                 "respaldo": p.respaldo},
            "reloj": {"restante": self.tiempo_restante, "activo": self.reloj_activo},
            "campana": None if self.campana is None else self.campana.to_dict(),
            "apoyo": self.apoyo, "por_rumores": self.por_rumores,
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
                             int(d.get("credibilidad", cred.INICIAL)), list(d.get("historial", [])))
                     for d in datos["jugadores"]]
        rng = random.Random()
        s = datos["rng"]
        rng.setstate((s[0], tuple(s[1]), s[2]))
        sesion = cls(jugadores, arboles, GrafoSocial.from_dict(datos["grafo"]), GrafoCiudad.cargar(ruta_mapa), rng,
                     CityState.from_dict(datos["ciudad"]))
        sesion.indice, sesion.turno, sesion.fase = indice, int(datos["turno"]), datos["fase"]
        sesion.apoyo.update(datos.get("apoyo", {}))
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
