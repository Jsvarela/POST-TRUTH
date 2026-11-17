"""Eleccion del alcalde: como las decisiones de la campaña mueven el apoyo de cada candidato. Logica pura.

Cada publicacion que toca a un candidato (events.json, "candidatos") lo favorece (+1) o lo perjudica (-1) SI
CIRCULA. Lo que hace el jugador decide cuanto circula:
- Falsa que se comparte, se ignora o se deja vencer: el rumor mueve el apoyo injustamente (mas con mas alcance).
- Falsa verificada o reportada: no dana y devuelve algo de lo perdido.
- Verdadera compartida: mueve el apoyo con razones legitimas; reportarla castiga al que dice la verdad.
Sin azar: el resultado depende de la habilidad del jugador para frenar rumores.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    sin_rumores: dict = field(default_factory=dict)   # % que habria sacado cada uno sin los rumores falsos


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
    """Apoyo que gana cada candidato por como quedo la ciudad (respecto a como empezo la campaña)."""
    inicio = CityState()
    return {c: sum(peso * (getattr(ciudad, campo) - getattr(inicio, campo)) for campo, peso in PERFILES[c].items())
            for c in CANDIDATOS}


ACCIONES = {"compartir": "Lo compartiste", "verificar": "Lo verificaste", "ignorar": "Lo ignoraste",
            "reportar": "Lo reportaste", "vencido": "Se te acabo el tiempo y no decidiste"}
INDICADOR = {"misinformation": ("la desinformacion", False), "trust": ("la confianza", False),
             "conflicts": ("los conflictos", True), "verified_information": ("la informacion verificada", False)}
VEREDICTO = {   # (falsa, accion) -> si estuvo bien o mal y por que: lo que el juego quiere que se aprenda
    (True, "compartir"): "Mal: compartir un rumor falso lo hizo llegar mas lejos.",
    (True, "verificar"): "Bien: verificarlo antes de compartir le quito fuerza.",
    (True, "reportar"): "Bien: reportarlo freno a quien lo regaba.",
    (True, "ignorar"): "Regular: ignorarlo no lo esparcio, pero tampoco lo freno.",
    (True, "vencido"): "Mal: sin decidir, el rumor corrio solo.",
    (False, "compartir"): "Bien: compartir algo cierto informo a la ciudad.",
    (False, "verificar"): "Bien: verificar antes de compartir siempre suma.",
    (False, "reportar"): "Mal: reportar algo cierto le resto confianza a la ciudad.",
    (False, "ignorar"): "Regular: era cierto y no ayudaste a que se supiera.",
    (False, "vencido"): "Regular: era cierto, pero se te paso el momento.",
}


MEDALLAS = ((75, "oro"), (55, "plata"), (35, "bronce"))   # puntos minimos (de 100) de cada una


def puntaje_final(ciudad, credibilidad: int, bitacora: list[dict]) -> tuple[int, str, list[tuple[str, int, int]]]:
    """(puntos de 0 a 100, medalla o "", desglose [(que, puntos, de cuantos)]): que tan bien se cuido la campaña."""
    dias = len(bitacora) or 1
    buenas = sum(VEREDICTO[(b["falsa"], b["accion"])].startswith("Bien") for b in bitacora)
    # lo bueno es que pocos crean lo falso y muchos lo cierto
    bien = [(100 - b["creyeron"]) if b["falsa"] else b["creyeron"] for b in bitacora if b.get("creyeron") is not None]
    frenado = sum(bien) / (100 * len(bien)) if bien else 0.0
    desglose = [("Ciudad informada", round(40 * (100 - ciudad.misinformation) / 100), 40),
                ("Tu credibilidad", round(25 * credibilidad / 100), 25),
                ("Decisiones acertadas", round(20 * buenas / dias), 20),
                ("La red creyo lo correcto", round(15 * frenado), 15)]
    total = sum(puntos for _, puntos, _ in desglose)
    return total, next((nombre for minimo, nombre in MEDALLAS if total >= minimo), ""), desglose


def explicar(bitacora: list[dict], r: "ResultadoEleccion", nombres: dict[str, str]) -> list[str]:
    """Una linea por dia (que publico @VerdadNova, que hiciste, a quien afecto y que dejo) y una de resumen:
    que peso mas en el ganador. Sin cifras del grafo: palabras como "mucho" o "algo"."""
    lineas = []
    for b in bitacora:
        partes = [f"Dia {b['dia']}: \"{b['titulo']}\" ({'falso' if b['falsa'] else 'cierto'}). {ACCIONES[b['accion']]}.",
                  VEREDICTO[(b["falsa"], b["accion"])]]
        for c, d in b["apoyo"].items():
            cuanto = "mucho" if abs(d) >= 5 else "algo"
            if d < 0:
                partes.append(f"{nombres[c]} perdio {cuanto} de apoyo" + (" injustamente." if b["falsa"] else "."))
            elif d > 0:
                partes.append(f"{nombres[c]} gano {cuanto} de apoyo" + (": lo protegiste." if b["falsa"] else "."))
        if b["creyeron"] is not None:
            partes.append(f"Despues de tu defensa lo creyo el {b['creyeron']}% de la red.")
        cambios = [f"{('subieron' if plural else 'subio') if b['ciudad'][k] > 0 else ('bajaron' if plural else 'bajo')} "
                   f"{nombre}" for k, (nombre, plural) in INDICADOR.items() if b["ciudad"].get(k)]
        if cambios:
            partes.append("En la ciudad " + ", ".join(cambios) + ".")
        lineas.append(" ".join(partes))
    ganador = nombres[r.ganador]
    if r.hundido_por_rumor:
        lineas.append(f"Resultado: gano {ganador}, pero sin los rumores falsos habria ganado {nombres[r.hundido_por_rumor]}. "
                      "Lo que se compartio sin verificar cambio la eleccion.")
    elif r.por_la_ciudad:
        lineas.append(f"Resultado: gano {ganador} por como quedo la ciudad, y la ciudad es la suma de tus decisiones.")
    else:
        lineas.append(f"Resultado: gano {ganador} por sus propuestas: los rumores no torcieron la eleccion.")
    return lineas


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
    total_sin = sum(max(APOYO_MINIMO, v) for v in sin_rumores.values())
    return ResultadoEleccion(votos, ganador, participacion(ciudad), justo if justo != ganador else "", titulo(ciudad),
                             por_ciudad, {c: 100 * max(APOYO_MINIMO, sin_rumores[c]) / total_sin for c in CANDIDATOS})
