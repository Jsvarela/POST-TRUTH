"""Vista del mundo caminable: camara que sigue al jugador, marcas de la noticia y la evidencia, guia de ruta,
HUD (indicadores y energia) y minimapa. Todo el arte del mundo pasa por un proveedor (ver arte_mundo).

El mundo (data/mundo.json) es mas grande que la pantalla: se ve una ventana de ANCHO/ESCALA x ALTO/ESCALA
pixeles del mundo alrededor del jugador, y la camara se detiene en los bordes del mundo.
"""
from dataclasses import dataclass

import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models.mundo import MundoCiudad
from post_truth.views.arte_mundo import ARTE_FORMAS, ArteFormas
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import RECT_HUD, _dibujar_energia, _dibujar_hud
from post_truth.views.iconos import rayo
from post_truth.views.mapa_view import _rombo
from post_truth.views.theme import Tema

AYUDA = "Caminar: WASD o flechas   |   E: entrar o buscar   |   G: guia   |   ESC: menu"
RECT_MINIMAPA = pygame.Rect(ANCHO - px(16) - px(220), RECT_HUD.bottom + px(12), px(220), px(138))


@dataclass
class EstadoMundo:
    """Lo que la vista necesita de la partida (la arma el controlador; la vista no decide nada)."""
    noticia: str = ""                          # zona de la noticia activa ("" si no hay)
    evidencias: frozenset | set = frozenset()  # zonas con evidencia pendiente de la noticia activa
    accion: tuple[str, str] | None = None      # (zona, "entrar" | "evidencia") disponible con E
    investigacion: object = None               # energia del jugador (energia, energia_max)
    indicadores: list = ()                     # filas del HUD (CityState.as_display_rows)
    guia: tuple[str, ...] = ()                 # ruta de plazas hacia la noticia (vacia: guia apagada)
    costo_guia: int | None = None
    aviso: str = ""
    color_rol: int = 0


def camara(mundo: MundoCiudad, ancho: int = ANCHO, alto: int = ALTO) -> tuple[float, float]:
    """Esquina superior izquierda (en pixeles del mundo) de lo que se ve: centrada en el jugador y sin salirse
    del mundo. Si el mundo es mas chico que la pantalla en un eje, se centra en ese eje."""
    vista_w, vista_h = ancho / ESCALA, alto / ESCALA
    mundo_w, mundo_h = mundo.tamano

    def eje(jugador: float, vista: float, total: float) -> float:
        if total <= vista:
            return (total - vista) / 2
        return min(max(jugador - vista / 2, 0.0), total - vista)
    return eje(mundo.jugador[0], vista_w, mundo_w), eje(mundo.jugador[1], vista_h, mundo_h)


def a_pantalla(p: tuple[float, float], cam: tuple[float, float]) -> tuple[int, int]:
    return px(p[0] - cam[0]), px(p[1] - cam[1])


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MundoCiudad,
                  estado: EstadoMundo | None = None, arte: ArteFormas = ARTE_FORMAS) -> None:
    estado = estado or EstadoMundo()
    cam = camara(mundo, *pantalla.get_size())
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
    arte.personaje(pantalla, tema, a_pantalla(mundo.jugador, cam), px(mundo.radio_jugador), estado.color_rol)
    if estado.indicadores:
        _dibujar_hud(pantalla, fuentes, tema, list(estado.indicadores))
    if estado.investigacion is not None:
        _dibujar_energia(pantalla, fuentes, tema, estado.investigacion, RECT_HUD.bottom + px(12))
    _minimapa(pantalla, tema, mundo, estado)
    if estado.guia and estado.costo_guia is not None:
        _costo_guia(pantalla, fuentes, tema, estado.costo_guia)
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
    if estado.guia and estado.costo_guia is not None:
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


def _costo_guia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, costo: int) -> None:
    """Bajo el minimapa: cuanto cuesta llegar a la noticia por la guia, en rayos (sin cifras sueltas)."""
    caja = pygame.Rect(RECT_MINIMAPA.x, RECT_MINIMAPA.bottom + px(8), RECT_MINIMAPA.w, px(40))
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(10))
    pygame.draw.rect(pantalla, tema.acento, caja, px(2), border_radius=px(10))
    # Por la guia (camino mas corto hacia la noticia) caminar es gratis; desviarse cuesta los rayos de cada calle
    texto = fuentes.chica.render("Por la guia: gratis" if costo == 0 else "Hasta la noticia:", True, tema.texto)
    pantalla.blit(texto, texto.get_rect(midleft=(caja.x + px(10), caja.centery)))
    for i in range(costo):
        rayo(pantalla, tema.acento, (caja.x + texto.get_width() + px(26) + i * px(20), caja.centery), px(9))
