"""Eleccion del alcalde: como las decisiones de la campana mueven el apoyo de cada candidato. Logica pura.

Cada publicacion que toca a un candidato (events.json, "candidatos") lo favorece (+1) o lo perjudica (-1) SI
CIRCULA. Lo que hace el jugador decide cuanto circula:
- Falsa que se comparte, se ignora o se deja vencer: el rumor mueve el apoyo injustamente (mas con mas alcance).
- Falsa verificada o reportada: no dana y devuelve algo de lo perdido.
- Verdadera compartida: mueve el apoyo con razones legitimas; reportarla castiga al que dice la verdad.
Sin azar: el resultado depende de la habilidad del jugador para frenar rumores.
"""
from __future__ import annotations

from dataclasses import dataclass

from post_truth.game_state import CityState

CANDIDATOS = ("juan", "maria", "andres", "lucia")   # los mismos ids de data/reparto.json
# Afinidad con la ciudad al final: cuanto gana cada uno por punto de cambio de un indicador desde el inicio.
# Lucia ("Hablemos claro") crece con la informacion verificada y la confianza; Maria con la convivencia; Andres con
# el bienestar digital; Juan ("mas orden") crece cuando hay conflictos.
PERFILES = {
    "juan": {"conflicts": 0.4},
    "maria": {"coexistence": 0.4},
    "andres": {"digital_wellbeing": 0.4},
    "lucia": {"verified_information": 0.2, "trust": 0.2},
}
APOYO_INICIAL = 25.0
PESO_RUMOR, PESO_VERDAD = 6.0, 4.0
APOYO_MINIMO = 1.0


def efecto_en_apoyo(sentido: int, falsa: bool, tipo: str, alcance: float, vencido: bool = False) -> float:
    """Cuanto se mueve el apoyo de un candidato por una decision. `alcance` es la fraccion de la red que la recibio."""
    circula = tipo in ("compartir", "ignorar", "") or vencido
    if falsa:
        if tipo == "compartir" or vencido:
            return sentido * PESO_RUMOR * (1 + alcance)
        if circula:
            return sentido * PESO_RUMOR * 0.5           # nadie la frena: sigue corriendo sola
        return -sentido * PESO_RUMOR * 0.25             # desmentida: el afectado recupera algo
    if tipo == "compartir":
        return sentido * PESO_VERDAD * (1 + alcance)
    if tipo == "verificar":
        return sentido * PESO_VERDAD * 0.5
    if tipo == "reportar":
        return -sentido * PESO_VERDAD * 0.5             # reportar algo cierto
    return 0.0


@dataclass(frozen=True)
class ResultadoEleccion:
    votos: dict[str, float]          # porcentaje de cada candidato (suma 100)
    ganador: str
    participacion: int               # % de la ciudad que voto
    hundido_por_rumor: str           # candidato que habria ganado sin rumores falsos ("" si nadie)
    titulo_jugador: str
    por_la_ciudad: bool = False      # el ganador debe mas a como quedo la ciudad que a sus propuestas


def participacion(ciudad) -> int:
    """La desinformacion y los conflictos alejan a la gente de las urnas; la informacion verificada la acerca."""
    p = 70 - 0.5 * (ciudad.misinformation - 35) - 0.5 * (ciudad.conflicts - 22) + 0.3 * (ciudad.verified_information - 55)
    return round(max(30.0, min(90.0, p)))


def titulo(ciudad) -> str:
    if ciudad.misinformation < 40 and ciudad.verified_information > 50:
        return "Guardian de Ciudad Nova"
    if ciudad.misinformation < 60:
        return "Ciudad dividida"
    return "Ciudad desinformada"


def afinidad(ciudad) -> dict[str, float]:
    """Apoyo que gana cada candidato por como quedo la ciudad (respecto a como empezo la campana)."""
    inicio = CityState()
    return {c: sum(peso * (getattr(ciudad, campo) - getattr(inicio, campo)) for campo, peso in PERFILES[c].items())
            for c in CANDIDATOS}


def calcular(apoyo_decisiones: dict[str, float], por_rumores: dict[str, float], ciudad) -> ResultadoEleccion:
    """Apoyo = lo que movieron las decisiones (rumores incluidos) + la afinidad con la ciudad final.
    `por_rumores`: la parte que movieron publicaciones FALSAS."""
    extra = afinidad(ciudad)
    apoyo = {c: max(APOYO_MINIMO, apoyo_decisiones[c] + extra[c]) for c in CANDIDATOS}
    total = sum(apoyo.values())
    votos = {c: 100 * apoyo[c] / total for c in CANDIDATOS}
    ganador = max(CANDIDATOS, key=lambda c: (apoyo[c], -CANDIDATOS.index(c)))
    sin_rumores = {c: apoyo[c] - por_rumores.get(c, 0.0) for c in CANDIDATOS}
    justo = max(CANDIDATOS, key=lambda c: (sin_rumores[c], -CANDIDATOS.index(c)))
    por_ciudad = extra[ganador] > apoyo_decisiones[ganador] - APOYO_INICIAL
    return ResultadoEleccion(votos, ganador, participacion(ciudad), justo if justo != ganador else "", titulo(ciudad),
                             por_ciudad)
