"""Mecanica: que le pasa al grafo social segun la decision del jugador."""
import random
from dataclasses import dataclass

from post_truth.models import Impact
from post_truth.structures.grafo_social import GrafoSocial, ResultadoPropagacion

COMPARTIR, VERIFICAR, REPORTAR, IGNORAR = "compartir", "verificar", "reportar", "ignorar"

FRENO_AUTOR = 0.35
FRENO_CONTACTOS = 0.6

FUERZA_VERIFICAR = {0: 0.15, 1: 0.4, 2: 1.0}
FUERZA_REPORTAR = {0: 0.0, 1: 0.3, 2: 1.0}
FACTOR_LIMITE_REPORTE = 0.6
REPORTE_INFUNDADO = Impact(trust=-3, score=-2)

UMBRAL_FALSA = 50

Arista = tuple[str, str]


def es_falsa(truth_level: int) -> bool:
    return truth_level < UMBRAL_FALSA


def _nivel(respaldo: int) -> int:
    return max(0, min(2, respaldo))


def fuerza_verificar(respaldo: int) -> float:
    """Fraccion del efecto de Verificar segun el respaldo reunido."""
    return FUERZA_VERIFICAR[_nivel(respaldo)]


def fuerza_reportar(respaldo: int) -> float:
    """Fraccion de los beneficios de Reportar segun el respaldo reunido."""
    return FUERZA_REPORTAR[_nivel(respaldo)]


def reporte_rechazado(respaldo: int) -> bool:
    """Un reporte sin ninguna prueba de falsedad se rechaza."""
    return _nivel(respaldo) == 0


def _pct(fuerza: float) -> int:
    return round(100 * fuerza)


def mensaje_respaldo(tipo: str, respaldo: int) -> str:
    """Frase que explica al jugador como pesaron sus pruebas en Verificar o Reportar."""
    n = _nivel(respaldo)
    if tipo == VERIFICAR:
        return {2: "Tu verificacion se apoyo en evidencia de campo: efecto completo.",
                1: f"Solo contaste con pistas de la tarjeta: la verificacion rinde al {_pct(FUERZA_VERIFICAR[1])}%.",
                0: f"Verificaste sin pruebas concretas: la verificacion rinde al {_pct(FUERZA_VERIFICAR[0])}%."}[n]
    if tipo == REPORTAR:
        return {2: "Reporte aceptado: se cortaron las conexiones del autor.",
                1: "Reporte con pruebas parciales: se limito al autor, pero sigue difundiendo.",
                0: "Reporte rechazado por falta de pruebas: pierdes confianza."}[n]
    return ""


@dataclass(frozen=True)
class SimulacionDecision:
    tipo: str
    autor: str
    resultado: ResultadoPropagacion
    aristas_cortadas: tuple[Arista, ...]
    aristas_debilitadas: tuple[Arista, ...]


def simular_decision(grafo: GrafoSocial, tipo: str, es_falsa: bool, jugador: str, autor: str,
                     rng: random.Random | None = None, respaldo: int = 2) -> SimulacionDecision | None:
    """Aplica al grafo el efecto de `tipo` y devuelve la propagacion resultante."""
    cortadas: list[Arista] = []
    debilitadas: list[Arista] = []
    if tipo == COMPARTIR:
        origen = jugador
    elif tipo == VERIFICAR:
        origen = autor
        if es_falsa:
            fuerza = fuerza_verificar(respaldo)
            contactos = [a.destino for a in grafo.vecinos(autor)]
            debilitadas += grafo.debilitar_salientes(autor, 1 - (1 - FRENO_AUTOR) * fuerza)
            for c in contactos:
                debilitadas += grafo.debilitar_salientes(c, 1 - (1 - FRENO_CONTACTOS) * fuerza)
    elif tipo == REPORTAR:
        if reporte_rechazado(respaldo):
            return None
        origen = autor
        if _nivel(respaldo) >= 2:
            cortadas += grafo.cortar_salientes(autor)
        else:
            debilitadas += grafo.debilitar_salientes(autor, FACTOR_LIMITE_REPORTE)
    else:
        return None
    resultado = grafo.propagar(origen, es_falsa, rng)
    return SimulacionDecision(tipo, autor, resultado, tuple(cortadas), tuple(debilitadas))
