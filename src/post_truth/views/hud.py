"""HUD compacto: cada indicador es un icono de forma propia con su barra animada. Desde L2 lo normal es el modo
"minimo" (dia, objetivo del paso y credibilidad); la "placa" con todos los indicadores sale en la pausa (P) y la
"fila" en el cierre del dia."""
import math
from dataclasses import dataclass

import pygame

from post_truth.config import ANCHO, px
from post_truth.views.componentes import BarraAnimada, Fuentes, ajustar_texto, panel, recortar
from post_truth.views.theme import TOKENS, Tema, esp

INDICADORES = (   # (nombre de as_display_rows, etiqueta corta, es malo que suba)
    ("Informacion verificada", "Verificada", False), ("Confianza ciudadana", "Confianza", False),
    ("Convivencia", "Convivencia", False), ("Bienestar digital", "Bienestar", False),
    ("Desinformacion", "Desinfo.", True), ("Conflictos", "Conflictos", True),
)
CREDIBILIDAD = "Credibilidad"
PLACA = pygame.Rect(px(16), px(16), px(292), px(276))
FILA = pygame.Rect(0, 0, ANCHO, px(56))
MINIMO = pygame.Rect(px(16), px(16), px(292), px(118))


@dataclass
class DatosHud:
    filas: list[tuple[str, int]]          # as_display_rows de la ciudad (incluye el puntaje)
    credibilidad: int | None = None
    modo: str = "fila"                    # "minimo" (esquina) / "barra" (arriba): L2; "placa" o "fila": todo
    dia: tuple[int, int] | None = None
    fase: str = ""
    fraccion_dia: float = 0.0
    origen: int = 0                       # id de la ciudad: si cambia (partida nueva) no se anima el salto
    objetivo: str = ""                    # modo minimo: lo que toca ahora (models/director.py)


def icono(pantalla: pygame.Surface, tema: Tema, nombre: str, centro: tuple[int, int], r: int) -> None:
    """Cada indicador tiene una forma distinta (se distinguen sin color)."""
    x, y = centro
    malo = nombre in ("Desinformacion", "Conflictos")
    c = tema.malo if malo else tema.bueno
    if nombre == "Informacion verificada":     # circulo con visto
        pygame.draw.circle(pantalla, c, centro, r)
        pygame.draw.lines(pantalla, tema.fondo, False, [(x - r * 0.5, y), (x - r * 0.1, y + r * 0.4),
                                                        (x + r * 0.5, y - r * 0.4)], max(2, r // 4))
    elif nombre == "Confianza ciudadana":      # corazon
        pygame.draw.circle(pantalla, c, (x - r // 2, y - r // 4), r // 2 + 1)
        pygame.draw.circle(pantalla, c, (x + r // 2, y - r // 4), r // 2 + 1)
        pygame.draw.polygon(pantalla, c, [(x - r, y - r // 6), (x + r, y - r // 6), (x, y + r)])
    elif nombre == "Convivencia":              # dos personas
        for dx in (-r // 2, r // 2):
            pygame.draw.circle(pantalla, c, (x + dx, y - r // 2), r // 3 + 1)
            pygame.draw.rect(pantalla, c, (x + dx - r // 3, y - r // 8, 2 * r // 3, r))
    elif nombre == "Bienestar digital":        # sol
        for k in range(8):
            a = k * math.pi / 4
            pygame.draw.line(pantalla, c, (x + math.cos(a) * r * 0.6, y + math.sin(a) * r * 0.6),
                             (x + math.cos(a) * r, y + math.sin(a) * r), max(1, r // 5))
        pygame.draw.circle(pantalla, c, centro, r // 2)
    elif nombre == "Desinformacion":           # triangulo con "!"
        pygame.draw.polygon(pantalla, c, [(x, y - r), (x + r, y + r * 0.8), (x - r, y + r * 0.8)])
        pygame.draw.line(pantalla, tema.fondo, (x, y - r * 0.3), (x, y + r * 0.2), max(2, r // 4))
    elif nombre == "Conflictos":               # rayo
        pygame.draw.polygon(pantalla, c, [(x + r * 0.2, y - r), (x - r * 0.6, y + r * 0.15), (x, y + r * 0.15),
                                          (x - r * 0.2, y + r), (x + r * 0.6, y - r * 0.15), (x, y - r * 0.15)])
    else:                                      # credibilidad: escudo
        pygame.draw.polygon(pantalla, tema.acento, [(x - r, y - r), (x + r, y - r), (x + r, y + r * 0.2),
                                                    (x, y + r), (x - r, y + r * 0.2)])


def posiciones(modo: str) -> dict[str, tuple[int, int]]:
    """Donde esta cada indicador en pantalla: ahi nacen sus textos flotantes."""
    if modo in ("minimo", "barra"):   # los indicadores no se ven: sus textos nacen apilados junto al HUD
        x, y = (MINIMO.right + px(8), MINIMO.y + px(10)) if modo == "minimo" else (px(16), FILA.bottom + px(12))
        return {n: (x, y + i * px(18)) for i, n in enumerate([i[0] for i in INDICADORES] + [CREDIBILIDAD])}
    if modo == "placa":
        y0 = PLACA.y + px(78)
        return {n: (PLACA.right + px(8), y0 + i * px(24)) for i, n in enumerate([i[0] for i in INDICADORES]
                                                                                + [CREDIBILIDAD])}
    paso = (FILA.w - px(140)) // (len(INDICADORES) + 1)
    return {n: (px(16) + i * paso + px(40), FILA.bottom + px(4))
            for i, n in enumerate([i[0] for i in INDICADORES] + [CREDIBILIDAD])}


def _valores(d: DatosHud) -> dict[str, int]:
    v = dict(d.filas)
    if d.credibilidad is not None:
        v[CREDIBILIDAD] = d.credibilidad
    return v


def dibujar(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, d: DatosHud,
            barras: dict[str, BarraAnimada] | None = None) -> None:
    barras = barras or {}
    valores = _valores(d)
    nombres = [i[0] for i in INDICADORES] + ([CREDIBILIDAD] if d.credibilidad is not None else [])
    etiquetas = {i[0]: i[1] for i in INDICADORES} | {CREDIBILIDAD: "Credibilidad"}
    puntaje = valores.get("Puntaje jugador", 0)
    if d.modo == "minimo":
        _minimo(pantalla, fuentes, tema, d, barras, valores)
        return
    if d.modo == "barra":
        _barra_minima(pantalla, fuentes, tema, d, barras, valores)
        return
    if d.modo == "placa":
        panel(pantalla, tema, PLACA, TOKENS.alfa_panel)
        x, y = PLACA.x + esp(3), PLACA.y + esp(2)
        if d.dia:
            pantalla.blit(fuentes.normal.render(f"Dia {d.dia[0]} de {d.dia[1]}", True, tema.texto), (x, y))
            _sol(pantalla, tema, pygame.Rect(PLACA.right - px(66), y + px(2), px(52), px(40)), d.fraccion_dia)
            if d.fase:
                pantalla.blit(fuentes.chica.render(d.fase, True, tema.acento), (x, y + fuentes.normal.get_linesize()))
        for n in nombres:
            cx, cy = posiciones("placa")[n]
            icono(pantalla, tema, n, (x + px(9), cy), px(8))
            pantalla.blit(fuentes.chica.render(etiquetas[n], True, tema.texto), (x + px(24), cy - px(10)))
            _barra(pantalla, tema, barras, n, valores[n], pygame.Rect(PLACA.x + px(140), cy - px(4), px(96), px(8)))
            img = fuentes.chica.render(str(valores[n]), True, tema.texto)
            pantalla.blit(img, img.get_rect(midright=(PLACA.right - esp(3), cy)))
        img = fuentes.chica.render(f"Puntaje {puntaje}", True, tema.texto)
        pantalla.blit(img, (x, PLACA.bottom - esp(2) - img.get_height()))
        return
    capa = pygame.Surface(FILA.size, pygame.SRCALPHA)
    capa.fill((*tema.panel, TOKENS.alfa_panel))
    pantalla.blit(capa, FILA)
    pygame.draw.line(pantalla, tema.borde, FILA.bottomleft, FILA.bottomright, px(2))
    for n in nombres:
        cx, _ = posiciones("fila")[n]
        x0 = cx - px(40)
        icono(pantalla, tema, n, (x0 + px(9), px(16)), px(8))
        pantalla.blit(fuentes.chica.render(f"{etiquetas[n]} {valores[n]}", True, tema.texto), (x0 + px(22), px(6)))
        _barra(pantalla, tema, barras, n, valores[n], pygame.Rect(x0, px(34), px(104), px(9)))
    img = fuentes.normal.render(f"Puntaje {puntaje}", True, tema.texto)
    pantalla.blit(img, img.get_rect(midright=(FILA.right - esp(3), FILA.centery)))


def _minimo(pantalla, fuentes: Fuentes, tema: Tema, d: DatosHud, barras, valores) -> None:
    panel(pantalla, tema, MINIMO, TOKENS.alfa_panel)
    x, y = MINIMO.x + esp(3), MINIMO.y + esp(2)
    if d.dia:
        pantalla.blit(fuentes.normal.render(f"Dia {d.dia[0]} de {d.dia[1]}", True, tema.texto), (x, y))
        _sol(pantalla, tema, pygame.Rect(MINIMO.right - px(66), y + px(2), px(52), px(36)), d.fraccion_dia)
    y += px(40)   # debajo del sol: el objetivo usa todo el ancho
    for linea in lineas_objetivo(d.objetivo, fuentes):
        pantalla.blit(fuentes.chica.render(linea, True, tema.acento), (x, y))
        y += fuentes.chica.get_linesize()
    if d.credibilidad is not None:
        cy = MINIMO.bottom - esp(3) - px(4)
        icono(pantalla, tema, CREDIBILIDAD, (x + px(9), cy), px(8))
        pantalla.blit(fuentes.chica.render("Credibilidad", True, tema.texto), (x + px(24), cy - px(10)))
        _barra(pantalla, tema, barras, CREDIBILIDAD, valores[CREDIBILIDAD],
               pygame.Rect(MINIMO.x + px(140), cy - px(4), px(96), px(8)))
        img = fuentes.chica.render(str(valores[CREDIBILIDAD]), True, tema.texto)
        pantalla.blit(img, img.get_rect(midright=(MINIMO.right - esp(3), cy)))


def lineas_objetivo(texto: str, fuentes: Fuentes) -> list[str]:
    """El objetivo del HUD de la calle en a lo sumo dos lineas del ancho de la caja."""
    return ajustar_texto(texto, fuentes.chica, MINIMO.w - 2 * esp(3))[:2] if texto else []


def _barra_minima(pantalla, fuentes: Fuentes, tema: Tema, d: DatosHud, barras, valores) -> None:
    """Lo mismo que el minimo, en una fila arriba (pantallas con contenido en la esquina)."""
    capa = pygame.Surface(FILA.size, pygame.SRCALPHA)
    capa.fill((*tema.panel, TOKENS.alfa_panel))
    pantalla.blit(capa, FILA)
    pygame.draw.line(pantalla, tema.borde, FILA.bottomleft, FILA.bottomright, px(2))
    x = esp(3)
    if d.dia:
        img = fuentes.normal.render(f"Dia {d.dia[0]} de {d.dia[1]}", True, tema.texto)
        pantalla.blit(img, img.get_rect(midleft=(x, FILA.centery)))
        x += img.get_width() + esp(4)
    fin = FILA.right - px(300)
    if d.objetivo:
        img = fuentes.chica.render(recortar(d.objetivo, fuentes.chica, fin - x - esp(3)), True, tema.acento)
        pantalla.blit(img, img.get_rect(midleft=(x, FILA.centery)))
    if d.credibilidad is not None:
        icono(pantalla, tema, CREDIBILIDAD, (fin + px(9), FILA.centery), px(8))
        pantalla.blit(fuentes.chica.render("Credibilidad", True, tema.texto), (fin + px(24), FILA.centery - px(10)))
        _barra(pantalla, tema, barras, CREDIBILIDAD, valores[CREDIBILIDAD],
               pygame.Rect(fin + px(150), FILA.centery - px(4), px(96), px(8)))
        img = fuentes.chica.render(str(valores[CREDIBILIDAD]), True, tema.texto)
        pantalla.blit(img, img.get_rect(midright=(FILA.right - esp(3), FILA.centery)))


def minimo(s, credibilidad: int, modo: str = "minimo") -> DatosHud:
    """El HUD de L2 a partir de la sesion: dia, objetivo del paso y credibilidad (solo lee)."""
    c, d = s.campana, s.director
    nombre = (lambda z: s.mapa.zona(z).nombre if z in s.mapa else z.capitalize())
    return DatosHud(s.ciudad.as_display_rows(), credibilidad, modo, (c.dia + 1, len(c.dias)) if c else None,
                    "", c.fraccion if c else 0.0, id(s.ciudad), d.objetivo(nombre) if d else "")


def _barra(pantalla, tema, barras, nombre, valor, rect) -> None:
    b = barras.get(nombre) or BarraAnimada(valor)
    malo = nombre in ("Desinformacion", "Conflictos")
    b.draw(pantalla, tema, rect, tema.acento if nombre == CREDIBILIDAD else tema.malo if malo else tema.bueno)


def _sol(pantalla: pygame.Surface, tema: Tema, arco: pygame.Rect, fraccion: float) -> None:
    """La hora sin cifras: un sol (luna al anochecer) que cruza un arco."""
    pygame.draw.arc(pantalla, tema.borde, arco, 0, math.pi, px(2))
    ang = math.pi * (1 - fraccion)
    astro = (round(arco.centerx + math.cos(ang) * arco.w / 2), round(arco.centery - math.sin(ang) * arco.h / 2))
    if fraccion > 0.8:   # luna: circulo con un mordisco
        pygame.draw.circle(pantalla, tema.texto, astro, px(6))
        pygame.draw.circle(pantalla, tema.panel, (astro[0] + px(3), astro[1] - px(2)), px(5))
    else:
        pygame.draw.circle(pantalla, tema.detalle, astro, px(6))
