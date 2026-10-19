"""Vista del mundo caminable: camara que sigue al jugador, marcas de la noticia y la evidencia, guia de ruta,
HUD (indicadores) y minimapa. Todo el arte del mundo pasa por un proveedor (ver arte_mundo).

El mundo (data/mundo.json) es mas grande que la pantalla: se ve una ventana de ANCHO/ESCALA x ALTO/ESCALA
pixeles del mundo alrededor del jugador, y la camara se detiene en los bordes del mundo.
"""
import math
from dataclasses import dataclass, field

import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models import Role
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.mundo import MundoCiudad
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.arte_mundo import ARTE_FORMAS, ArteFormas
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import RECT_HUD, _dibujar_hud
from post_truth.views.mapa_view import _rombo
from post_truth.views.theme import Tema

AYUDA = "Caminar: WASD o flechas   |   E: entrar o buscar   |   G: guia   |   ESC: menu"
ALTO_PERSONAJE = 3.2   # alto del personaje en radios de colision del jugador
RECT_MINIMAPA = pygame.Rect(ANCHO - px(16) - px(220), RECT_HUD.bottom + px(12), px(220), px(138))


@dataclass
class EstadoMundo:
    """Lo que la vista necesita de la partida (la arma el controlador; la vista no decide nada)."""
    noticia: str = ""                          # zona de la noticia activa ("" si no hay)
    evidencias: frozenset | set = frozenset()  # zonas con evidencia pendiente de la noticia activa
    accion: tuple[str, str] | None = None      # (zona, "entrar" | "evidencia") disponible con E
    indicadores: list = ()                     # filas del HUD (CityState.as_display_rows)
    guia: tuple[str, ...] = ()                 # ruta de plazas hacia la noticia (vacia: guia apagada)
    aviso: str = ""
    personaje: Personaje = Personaje(Role.CITIZEN, Genero.MUJER)
    centro_camara: tuple[float, float] | None = None   # centro suavizado (Camara); None = sobre el jugador
    animacion: AnimacionPersonaje = field(default_factory=AnimacionPersonaje)


class Camara:
    """Centro de la vista que persigue al jugador con amortiguacion exponencial: cada cuadro recorre la fraccion
    1 - e^(-SUAVIDAD * dt) de lo que le falta. Como la fraccion depende de dt y no del numero de cuadros, la
    camara llega igual a 30 y a 60 FPS (es la solucion exacta de x' = SUAVIDAD * (objetivo - x))."""
    SUAVIDAD = 8.0   # 1/s: a los ~0.3 s ya recorrio el 90% del camino

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
    """Esquina superior izquierda (en pixeles del mundo) de lo que se ve: centrada en `centro` (por defecto el
    jugador) y sin salirse del mundo. Si el mundo es mas chico que la pantalla en un eje, se centra en ese eje."""
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


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MundoCiudad,
                  estado: EstadoMundo | None = None, arte: ArteFormas = ARTE_FORMAS) -> None:
    estado = estado or EstadoMundo()
    cam = camara(mundo, *pantalla.get_size(), estado.centro_camara)
    arte.suelo(pantalla, tema)
    for c in mundo.calles:
        arte.calle(pantalla, tema, a_pantalla(mundo.plazas[c.desde].pos, cam), a_pantalla(mundo.plazas[c.hasta].pos, cam),
                   px(c.ancho))
    for p in mundo.plazas.values():
        arte.plaza(pantalla, tema, a_pantalla(p.pos, cam), px(p.radio))
    if estado.guia:
        _guia(pantalla, tema, mundo, cam, estado.guia)
    resaltada = estado.accion[0] if estado.accion else None
    for e in mundo.edificios:
        x, y, w, h = e.rect
        rect = pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h))
        if not rect.colliderect(pantalla.get_rect()):
            continue
        arte.edificio(pantalla, tema, fuentes, e.zona, e.zona.capitalize(), rect, e.zona == resaltada)
        if e.zona == estado.noticia:
            _globo_noticia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(8)))
        elif e.zona in estado.evidencias:
            _marca_evidencia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(26)))
    # los pies van al borde inferior del circulo de colision; el cuerpo sobresale hacia arriba
    x, y = mundo.jugador
    arte.personaje(pantalla, tema, a_pantalla((x, y + mundo.radio_jugador), cam), px(ALTO_PERSONAJE * mundo.radio_jugador),
                   estado.personaje, estado.animacion.nombre, estado.animacion.cuadro)
    if estado.indicadores:
        _dibujar_hud(pantalla, fuentes, tema, list(estado.indicadores))
    _minimapa(pantalla, tema, mundo, estado)
    _franja(pantalla, fuentes, tema, _mensaje(estado))


# --- marcas sobre los lugares (forma propia, no solo color) ---------------------------------------
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
    """Rombo con "?" (el mismo del minimapa de la escena): aqui hay evidencia de la noticia por buscar."""
    _rombo(pantalla, tema.texto, centro, px(20), True)
    _rombo(pantalla, tema.detalle, centro, px(16), True)
    img = fuentes.normal.render("?", True, tema.fondo)
    pantalla.blit(img, img.get_rect(center=centro))


def _guia(pantalla: pygame.Surface, tema: Tema, mundo: MundoCiudad, cam: tuple[float, float],
          ruta: tuple[str, ...]) -> None:
    """Ruta tenue (camino mas corto, Dijkstra) por el centro de las calles: puntos espaciados, no una linea solida."""
    capa = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    color = (*tema.acento, 150)
    for a, b in zip(ruta, ruta[1:]):
        (x1, y1), (x2, y2) = a_pantalla(mundo.plazas[a].pos, cam), a_pantalla(mundo.plazas[b].pos, cam)
        largo = max(1, round(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / px(26)))
        for i in range(largo + 1):
            pygame.draw.circle(capa, color, (x1 + (x2 - x1) * i // largo, y1 + (y2 - y1) * i // largo), px(6))
    pantalla.blit(capa, (0, 0))


# --- minimapa y franja inferior ---------------------------------------------------------------------
def _minimapa(pantalla: pygame.Surface, tema: Tema, mundo: MundoCiudad, estado: EstadoMundo) -> None:
    """Toda la ciudad en pequeno: calles, plazas, la noticia (cuadrado), la evidencia (rombo) y el jugador (circulo)."""
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
    if estado.noticia in mundo.plazas:      # la noticia: un cuadrado (forma distinta a la del jugador)
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
    if estado.accion is not None:
        zona, que = estado.accion
        return f"E: entrar a {zona.capitalize()}" if que == "entrar" else f"E: buscar evidencia en {zona.capitalize()}"
    if estado.guia:
        return f"Guia: la noticia esta en {estado.noticia.capitalize()}"
    return ""


def _franja(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mensaje: str) -> None:
    """Franja inferior: el mensaje del momento (accion con E, aviso o guia) y los controles."""
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
