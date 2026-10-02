"""Mecanica: que le pasa al grafo social segun la decision del jugador. Logica pura (sin pygame).

Separa las REGLAS DEL JUEGO (que hace cada accion) de la ESTRUCTURA (`GrafoSocial`, que solo
sabe agregar/quitar y propagar). Asi el servidor de sockets puede reutilizarlo tal cual.

    compartir -> la publicacion parte del JUGADOR (su rol cuenta: un Influencer llega mas lejos).
    verificar -> si es falsa, frena su difusion: el autor y sus contactos directos transmiten
                 con menos peso (se ven aristas mas finas). Si es verdadera, no hay nada que
                 frenar y se difunde con normalidad desde su autor.
    reportar  -> la cuenta del autor deja de difundir: se ELIMINAN sus aristas salientes.
    ignorar   -> no se simula nada (la publicacion no se mueve por decision del jugador).

Verificar y Reportar modifican el grafo de forma persistente: lo que cortas o frenas sigue
cortado o frenado en las siguientes publicaciones de la partida.

RESPALDO (no hace falta ir a ningun lugar; importa lo que se reunio, ver Investigacion.respaldo):
    nivel 0 = nada, 1 = solo pistas de la tarjeta, 2 = evidencia de campo (del mapa de la ciudad).

                 Verificar (efecto sobre beneficios y friccion)      Reportar
    nivel 0      50%                                                 rechazado: no pasa nada y baja la confianza
    nivel 1      75%                                                 limita al autor (le baja el peso a sus conexiones)
    nivel 2      100%                                                aceptado: se cortan las conexiones del autor

El respaldo solo atenua los efectos BENEFICIOSOS (ver Impact.atenuar_beneficios); los perjuicios de
equivocarse no se atenuan. Reportar una noticia verdadera nunca tiene pruebas de falsedad, asi que
siempre queda rechazado.
"""
import random
from dataclasses import dataclass

from post_truth.models import Impact
from post_truth.structures.grafo_social import GrafoSocial, ResultadoPropagacion

COMPARTIR, VERIFICAR, REPORTAR, IGNORAR = "compartir", "verificar", "reportar", "ignorar"

FRENO_AUTOR = 0.35      # el peso de las aristas del autor se multiplica por esto al verificar
FRENO_CONTACTOS = 0.6   # y el de las aristas de sus contactos directos (contencion a 2 saltos)

# Fraccion de efecto segun el respaldo (0, 1 o 2) de cada accion
FUERZA_VERIFICAR = {0: 0.5, 1: 0.75, 2: 1.0}
FUERZA_REPORTAR = {0: 0.0, 1: 0.6, 2: 1.0}
FACTOR_LIMITE_REPORTE = 0.5          # con respaldo 1, las conexiones del autor pierden la mitad de su peso
REPORTE_INFUNDADO = Impact(trust=-3, score=-2)   # reportar sin ninguna prueba: la plataforma lo rechaza

UMBRAL_FALSA = 50       # truth_level por debajo de esto se trata como noticia falsa (rumor, fake, manipulada)

Arista = tuple[str, str]


def es_falsa(truth_level: int) -> bool:
    return truth_level < UMBRAL_FALSA


def _nivel(respaldo: int) -> int:
    return max(0, min(2, respaldo))


def fuerza_verificar(respaldo: int) -> float:
    """Fraccion (0.5, 0.75 o 1.0) del efecto de Verificar segun el respaldo reunido."""
    return FUERZA_VERIFICAR[_nivel(respaldo)]


def fuerza_reportar(respaldo: int) -> float:
    """Fraccion (0, 0.6 o 1.0) de los beneficios de Reportar segun el respaldo reunido."""
    return FUERZA_REPORTAR[_nivel(respaldo)]


def reporte_rechazado(respaldo: int) -> bool:
    """Un reporte sin ninguna prueba de falsedad se rechaza."""
    return _nivel(respaldo) == 0


def mensaje_respaldo(tipo: str, respaldo: int) -> str:
    """Frase que explica al jugador como pesaron sus pruebas en Verificar o Reportar ("" para otras acciones)."""
    n = _nivel(respaldo)
    if tipo == VERIFICAR:
        return {2: "Tu verificacion se apoyo en evidencia de campo: efecto completo.",
                1: "Solo contaste con pistas de la tarjeta: la verificacion rinde al 75%.",
                0: "Verificaste sin pruebas concretas: la verificacion rinde al 50%."}[n]
    if tipo == REPORTAR:
        return {2: "Reporte aceptado: se cortaron las conexiones del autor.",
                1: "Reporte con pruebas parciales: se limito al autor, pero sigue difundiendo.",
                0: "Reporte rechazado por falta de pruebas: pierdes confianza."}[n]
    return ""


@dataclass(frozen=True)
class SimulacionDecision:
    tipo: str
    autor: str                              # quien publico originalmente la noticia
    resultado: ResultadoPropagacion
    aristas_cortadas: tuple[Arista, ...]    # eliminadas (Reportar)
    aristas_debilitadas: tuple[Arista, ...]  # con peso reducido (Verificar)


def simular_decision(grafo: GrafoSocial, tipo: str, es_falsa: bool, jugador: str, autor: str,
                     rng: random.Random | None = None, respaldo: int = 2) -> SimulacionDecision | None:
    """Aplica al grafo el efecto de `tipo` y devuelve la propagacion resultante.
    Devuelve None cuando la decision no mueve la publicacion (ignorar, tipo desconocido o un reporte
    rechazado por falta de pruebas). `respaldo` (0, 1 o 2) gradua Verificar y Reportar."""
    cortadas: list[Arista] = []
    debilitadas: list[Arista] = []
    if tipo == COMPARTIR:
        origen = jugador
    elif tipo == VERIFICAR:
        origen = autor
        if es_falsa:
            # Con poco respaldo el freno es mas suave: el factor se acerca a 1 (sin efecto) cuando fuerza -> 0
            fuerza = fuerza_verificar(respaldo)
            contactos = [a.destino for a in grafo.vecinos(autor)]
            debilitadas += grafo.debilitar_salientes(autor, 1 - (1 - FRENO_AUTOR) * fuerza)
            for c in contactos:
                debilitadas += grafo.debilitar_salientes(c, 1 - (1 - FRENO_CONTACTOS) * fuerza)
    elif tipo == REPORTAR:
        if reporte_rechazado(respaldo):
            return None                  # sin pruebas no pasa nada en el grafo
        origen = autor
        if _nivel(respaldo) >= 2:
            cortadas += grafo.cortar_salientes(autor)        # aceptado: la cuenta deja de difundir
        else:
            debilitadas += grafo.debilitar_salientes(autor, FACTOR_LIMITE_REPORTE)   # limitado
    else:
        return None
    resultado = grafo.propagar(origen, es_falsa, rng)
    return SimulacionDecision(tipo, autor, resultado, tuple(cortadas), tuple(debilitadas))
