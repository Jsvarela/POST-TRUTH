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
"""
import random
from dataclasses import dataclass

from post_truth.structures.grafo_social import GrafoSocial, ResultadoPropagacion

COMPARTIR, VERIFICAR, REPORTAR, IGNORAR = "compartir", "verificar", "reportar", "ignorar"

FRENO_AUTOR = 0.35      # el peso de las aristas del autor se multiplica por esto al verificar
FRENO_CONTACTOS = 0.6   # y el de las aristas de sus contactos directos (contencion a 2 saltos)

UMBRAL_FALSA = 50       # truth_level por debajo de esto se trata como noticia falsa (rumor, fake, manipulada)

Arista = tuple[str, str]


def es_falsa(truth_level: int) -> bool:
    return truth_level < UMBRAL_FALSA


@dataclass(frozen=True)
class SimulacionDecision:
    tipo: str
    autor: str                              # quien publico originalmente la noticia
    resultado: ResultadoPropagacion
    aristas_cortadas: tuple[Arista, ...]    # eliminadas (Reportar)
    aristas_debilitadas: tuple[Arista, ...]  # con peso reducido (Verificar)


def simular_decision(grafo: GrafoSocial, tipo: str, es_falsa: bool, jugador: str, autor: str,
                     rng: random.Random | None = None) -> SimulacionDecision | None:
    """Aplica al grafo el efecto de `tipo` y devuelve la propagacion resultante.
    Devuelve None cuando la decision no mueve la publicacion (ignorar o tipo desconocido)."""
    cortadas: list[Arista] = []
    debilitadas: list[Arista] = []
    if tipo == COMPARTIR:
        origen = jugador
    elif tipo == VERIFICAR:
        origen = autor
        if es_falsa:
            contactos = [a.destino for a in grafo.vecinos(autor)]
            debilitadas += grafo.debilitar_salientes(autor, FRENO_AUTOR)
            for c in contactos:
                debilitadas += grafo.debilitar_salientes(c, FRENO_CONTACTOS)
    elif tipo == REPORTAR:
        origen = autor
        cortadas += grafo.cortar_salientes(autor)
    else:
        return None
    resultado = grafo.propagar(origen, es_falsa, rng)
    return SimulacionDecision(tipo, autor, resultado, tuple(cortadas), tuple(debilitadas))
