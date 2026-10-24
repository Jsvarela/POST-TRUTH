"""Vista del mundo caminable."""
import math
from dataclasses import dataclass, field

import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models import Role
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.mundo import MundoCiudad
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.arte_mundo import ARTE_FORMAS, ArteFormas
from post_truth.views.decorado import Decorado
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import RECT_HUD, _dibujar_hud, dibujar_reloj
from post_truth.views.mapa_view import _rombo
from post_truth.views.theme import TEMAS, Tema

AYUDA = "WASD: caminar   |   E: entrar o buscar   |   G: guia   |   H: habilidad   |   Y: aliados   |   ESC: menu"
ALTO_PERSONAJE = 3.2
PAJAROS = ((260, 70, 0.0), (300, 70, 0.6), (1100, -55, 9.0))
RECT_MINIMAPA = pygame.Rect(ANCHO - px(16) - px(220), RECT_HUD.bottom + px(12), px(220), px(138))


@dataclass
class EstadoMundo:
    """Lo que la vista necesita de la partida."""
    noticia: str = ""
    evidencias: frozenset | set = frozenset()
    accion: tuple[str, str] | None = None
    indicadores: list = ()
    guia: tuple[str, ...] = ()
    aviso: str = ""
    personaje: Personaje = Personaje(Role.CITIZEN, Genero.MUJER)
    centro_camara: tuple[float, float] | None = None
    decorado: Decorado | None = None
    t: float = 0.0
    reloj: tuple[float, float] | None = None   # (restante, total) del reloj de una publicacion viral
    dia: tuple[int, int] | None = None         # (dia, total) de la campana
    fraccion_dia: float = 0.0                  # 0 amanecer .. 1 noche
    credibilidad: int | None = None
    menu: tuple[str, ...] = ()                 # opciones del lugar abiertas con E (se eligen con 1-3)
    texto_accion: str = ""                     # que hace E aqui, cuando hay una sola opcion
    animacion: AnimacionPersonaje = field(default_factory=AnimacionPersonaje)


class Camara:
    """Centro de la vista que persigue al jugador con amortiguacion exponencial."""
    SUAVIDAD = 8.0

    def __init__(self, centro: tuple[float, float] = (0.0, 0.0)) -> None:
        self.centro = centro

    def saltar(self, objetivo: tuple[float, float]) -> None:
        """Sin transicion: al empezar una partida o al volver de un lugar la camara no "viaja" por el mapa."""
        self.centro = objetivo

    def seguir(self, objetivo: tuple[float, float], dt: float) -> None:
        f = 1 - math.exp(-self.SUAVIDAD * max(0.0, dt))
        self.centro = (self.centro[0] + (objetivo[0] - self.centro[0]) * f,
                       self.centro[1] + (objetivo[1] - self.centro[1]) * f)


def camara(mundo: MundoCiudad, ancho: int = ANCHO, alto: int = ALTO,
           centro: tuple[float, float] | None = None) -> tuple[float, float]:
    """Esquina superior izquierda de lo que se ve: centrada en `centro` y sin salirse del mundo."""
    vista_w, vista_h = ancho / ESCALA, alto / ESCALA
    mundo_w, mundo_h = mundo.tamano

    def eje(jugador: float, vista: float, total: float) -> float:
        if total <= vista:
            return (total - vista) / 2
        return min(max(jugador - vista / 2, 0.0), total - vista)
    cx, cy = centro if centro is not None else mundo.jugador
    return eje(cx, vista_w, mundo_w), eje(cy, vista_h, mundo_h)


def a_pantalla(p: tuple[float, float], cam: tuple[float, float]) -> tuple[int, int]:
    return px(p[0] - cam[0]), px(p[1] - cam[1])


def _anochecer(fraccion: float) -> float:
    """0 de dia; sube de 0 a 1 entre el 60% y el 100% del dia."""
    return max(0.0, min(1.0, (fraccion - 0.6) / 0.4))


def _velo_del_dia(pantalla: pygame.Surface, tema: Tema, fraccion: float) -> None:
    """Tarde calida y anochecer oscuro, con colores del tema; en alto contraste el velo es mas suave."""
    tarde = max(0.0, min(1.0, (fraccion - 0.4) / 0.3)) * (1 - _anochecer(fraccion))
    suave = 0.5 if tema is TEMAS["alto_contraste"] else 1.0
    capa = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    if tarde:
        capa.fill((*tema.detalle, round(28 * tarde * suave)))
    noche = _anochecer(fraccion)
    if noche:
        capa.fill((*tema.fondo, round(120 * noche * suave)))
    pantalla.blit(capa, (0, 0))


def _dibujar_dia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, dia: int, total: int, fraccion: float,
                 topleft: tuple[int, int]) -> None:
    """Dia de campana y un sol (luego luna) que cruza un arco: la hora sin cifras."""
    caja = pygame.Rect(*topleft, px(200), px(40))
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(8))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(8))
    img = fuentes.normal.render(f"Dia {dia} de {total}", True, tema.texto)
    pantalla.blit(img, img.get_rect(midleft=(caja.x + px(10), caja.centery)))
    arco = pygame.Rect(caja.right - px(78), caja.y + px(8), px(66), px(52))
    pygame.draw.arc(pantalla, tema.borde, arco, 0, math.pi, px(2))
    ang = math.pi * (1 - fraccion)
    astro = (round(arco.centerx + math.cos(ang) * arco.w / 2), round(arco.centery - math.sin(ang) * arco.h / 2))
    if _anochecer(fraccion) > 0.5:   # luna: circulo con un mordisco
        pygame.draw.circle(pantalla, tema.texto, astro, px(7))
        pygame.draw.circle(pantalla, tema.panel, (astro[0] + px(3), astro[1] - px(2)), px(6))
    else:
        pygame.draw.circle(pantalla, tema.detalle, astro, px(7))


def _vista(mundo: MundoCiudad, cam: tuple[float, float], pantalla: pygame.Surface, margen: float = 90):
    """Funcion que dice si un punto del mundo cae en pantalla."""
    ancho, alto = pantalla.get_size()
    x0, y0, x1, y1 = cam[0] - margen, cam[1] - margen, cam[0] + ancho / ESCALA + margen, cam[1] + alto / ESCALA + margen
    return lambda x, y: x0 <= x <= x1 and y0 <= y <= y1


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MundoCiudad,
                  estado: EstadoMundo | None = None, arte: ArteFormas = ARTE_FORMAS) -> None:
    estado = estado or EstadoMundo()
    cam = camara(mundo, *pantalla.get_size(), estado.centro_camara)
    arte.suelo(pantalla, tema)
    deco = estado.decorado
    visible = _vista(mundo, cam, pantalla)
    if deco is not None:
        for x, y, variante in deco.cesped:
            if visible(x, y):
                arte.cesped(pantalla, tema, a_pantalla((x, y), cam), px(7), variante)
    for c in mundo.calles:
        arte.calle(pantalla, tema, a_pantalla(mundo.plazas[c.desde].pos, cam), a_pantalla(mundo.plazas[c.hasta].pos, cam),
                   px(c.ancho))
    for p in mundo.plazas.values():
        arte.plaza(pantalla, tema, a_pantalla(p.pos, cam), px(p.radio))
    if deco is not None:
        for x, y in deco.bancas:
            if visible(x, y):
                arte.banca(pantalla, tema, a_pantalla((x, y), cam), px(30))
        for x, y, tam, flores in deco.arbustos:
            if visible(x, y):
                arte.arbusto(pantalla, tema, a_pantalla((x, y), cam), px(16 * tam), flores)
        luz = 0.15 + 0.85 * _anochecer(estado.fraccion_dia) if estado.dia else 1.0   # se encienden al atardecer
        for x, y, fase in deco.faroles:
            if visible(x, y):
                arte.farol(pantalla, tema, a_pantalla((x, y), cam), px(48),
                           luz * (0.5 + 0.5 * math.sin(estado.t * 1.5 + fase)))
    if estado.guia:
        _guia(pantalla, tema, mundo, cam, estado.guia)
    resaltada = estado.accion[0] if estado.accion else None
    for e in mundo.edificios:
        x, y, w, h = e.rect
        rect = pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h))
        if not rect.colliderect(pantalla.get_rect()):
            continue
        arte.edificio(pantalla, tema, fuentes, e.zona, e.zona.capitalize(), rect, e.zona == resaltada, estado.t)
        if e.zona == estado.noticia:
            _globo_noticia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(8)))
        elif e.zona in estado.evidencias:
            _marca_evidencia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(26)))
    if deco is not None:
        for x, y, tam, fase in deco.arboles:
            if visible(x, y):
                arte.arbol(pantalla, tema, a_pantalla((x, y), cam), px(34 * tam), math.sin(estado.t * 1.3 + fase))
    x, y = mundo.jugador
    arte.personaje(pantalla, tema, a_pantalla((x, y + mundo.radio_jugador), cam), px(ALTO_PERSONAJE * mundo.radio_jugador),
                   estado.personaje, estado.animacion.nombre, estado.animacion.cuadro)
    if deco is not None:
        ancho = mundo.tamano[0] + 400
        for i, (y0, v, desfase) in enumerate(PAJAROS):
            bx = (y0 * 3 + v * (estado.t + desfase)) % ancho - 200
            by = y0 + 25 * math.sin(estado.t * 0.8 + i)
            if visible(bx, by):
                arte.pajaro(pantalla, tema, a_pantalla((bx, by), cam), px(9), math.sin(estado.t * 9 + i * 1.7))
    if estado.dia:
        _velo_del_dia(pantalla, tema, estado.fraccion_dia)
    if estado.indicadores:
        _dibujar_hud(pantalla, fuentes, tema, list(estado.indicadores), estado.credibilidad)
    _minimapa(pantalla, tema, mundo, estado)
    y = RECT_HUD.bottom + px(12)
    if estado.dia:
        _dibujar_dia(pantalla, fuentes, tema, *estado.dia, estado.fraccion_dia, (px(16), y))
        y += px(48)
    if estado.reloj is not None:
        dibujar_reloj(pantalla, fuentes, tema, *estado.reloj, (px(16), y))
    _franja(pantalla, fuentes, tema, _mensaje(estado))


def _globo_noticia(pantalla: pygame.Surface, tema: Tema, fuentes: Fuentes, punta: tuple[int, int]) -> None:
    """Globo de dialogo con "!": aqui ocurre la noticia activa."""
    x, y = punta
    caja = pygame.Rect(0, 0, px(46), px(40))
    caja.midbottom = (x, y - px(12))
    pygame.draw.polygon(pantalla, tema.texto, [(x - px(9), caja.bottom - px(2)), (x + px(9), caja.bottom - px(2)), (x, y)])
    pygame.draw.rect(pantalla, tema.texto, caja.inflate(px(6), px(6)), border_radius=px(12))
    pygame.draw.rect(pantalla, tema.malo, caja, border_radius=px(10))
    img = fuentes.titulo.render("!", True, tema.texto)
    pantalla.blit(img, img.get_rect(center=caja.center))


def _marca_evidencia(pantalla: pygame.Surface, tema: Tema, fuentes: Fuentes, centro: tuple[int, int]) -> None:
    """Rombo con "?": aqui hay evidencia de la noticia por buscar."""
    _rombo(pantalla, tema.texto, centro, px(20), True)
    _rombo(pantalla, tema.detalle, centro, px(16), True)
    img = fuentes.normal.render("?", True, tema.fondo)
    pantalla.blit(img, img.get_rect(center=centro))


def _guia(pantalla: pygame.Surface, tema: Tema, mundo: MundoCiudad, cam: tuple[float, float],
          ruta: tuple[str, ...]) -> None:
    """Ruta tenue por el centro de las calles: puntos espaciados, no una linea solida."""
    capa = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    color = (*tema.acento, 150)
    for a, b in zip(ruta, ruta[1:]):
        (x1, y1), (x2, y2) = a_pantalla(mundo.plazas[a].pos, cam), a_pantalla(mundo.plazas[b].pos, cam)
        largo = max(1, round(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / px(26)))
        for i in range(largo + 1):
            pygame.draw.circle(capa, color, (x1 + (x2 - x1) * i // largo, y1 + (y2 - y1) * i // largo), px(6))
    pantalla.blit(capa, (0, 0))


def _minimapa(pantalla: pygame.Surface, tema: Tema, mundo: MundoCiudad, estado: EstadoMundo) -> None:
    """Toda la ciudad en pequeno: calles, plazas, la noticia, la evidencia y el jugador."""
    r = RECT_MINIMAPA
    pygame.draw.rect(pantalla, tema.panel, r, border_radius=px(10))
    pygame.draw.rect(pantalla, tema.borde, r, px(2), border_radius=px(10))
    interior = r.inflate(-px(20), -px(20))
    ancho, alto = mundo.tamano

    def m(p: tuple[float, float]) -> tuple[int, int]:
        return interior.x + round(p[0] / ancho * interior.w), interior.y + round(p[1] / alto * interior.h)
    for c in mundo.calles:
        pygame.draw.line(pantalla, tema.borde, m(mundo.plazas[c.desde].pos), m(mundo.plazas[c.hasta].pos), px(3))
    for p in mundo.plazas.values():
        pygame.draw.circle(pantalla, tema.borde, m(p.pos), px(5))
    if estado.noticia in mundo.plazas:
        caja = pygame.Rect(0, 0, px(12), px(12))
        caja.center = m(mundo.plazas[estado.noticia].pos)
        pygame.draw.rect(pantalla, tema.texto, caja.inflate(px(4), px(4)))
        pygame.draw.rect(pantalla, tema.malo, caja)
    for z in estado.evidencias:
        if z in mundo.plazas:
            _rombo(pantalla, tema.detalle, m(mundo.plazas[z].pos), px(6), True)
    pygame.draw.circle(pantalla, tema.texto, m(mundo.jugador), px(6))
    pygame.draw.circle(pantalla, tema.acento, m(mundo.jugador), px(4))


def _mensaje(estado: EstadoMundo) -> str:
    if estado.aviso:
        return estado.aviso
    if estado.menu:
        return " | ".join(f"{i + 1}: {o}" for i, o in enumerate(estado.menu)) + " | E: cerrar"
    if estado.accion is not None:
        zona, que = estado.accion
        if que == "elegir":
            return f"E: ver que hacer en {zona.capitalize()}"
        return f"E: {estado.texto_accion[0].lower()}{estado.texto_accion[1:]}" if estado.texto_accion else ""
    if estado.guia:
        return f"Guia: la noticia esta en {estado.noticia.capitalize()}"
    return ""


def _franja(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mensaje: str) -> None:
    """Franja inferior: el mensaje del momento y los controles."""
    ancho, alto = pantalla.get_size()
    lineas = ajustar_texto(mensaje, fuentes.normal, ancho - px(70)) if mensaje else []
    alto_caja = px(30) + max(1, len(lineas)) * fuentes.normal.get_linesize() + fuentes.chica.get_linesize()
    caja = pygame.Rect(px(16), alto - alto_caja - px(14), ancho - px(32), alto_caja)
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(12))
    y = caja.y + px(10)
    for linea in lineas:
        img = fuentes.normal.render(linea, True, tema.acento)
        pantalla.blit(img, (caja.x + px(18), y))
        y += fuentes.normal.get_linesize()
    ayuda = fuentes.chica.render(AYUDA, True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(bottomright=(caja.right - px(18), caja.bottom - px(8))))
