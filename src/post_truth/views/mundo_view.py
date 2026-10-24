"""Vista del mundo caminable."""
import math
from dataclasses import dataclass, field

import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models import Role
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.arte_mundo import ARTE_FORMAS, ArteFormas
from post_truth.views.decorado import Decorado
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import RECT_HUD, _dibujar_hud, dibujar_reloj
from post_truth.views.mapa_view import _rombo
from post_truth.views.theme import TEMAS, Tema

AYUDA = "WASD: caminar   |   E: entrar o buscar   |   G: guia   |   H: habilidad   |   Y: aliados   |   F3   |   ESC: menu"
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
    guia: tuple[str, ...] = ()                 # zonas de la ruta de la guia (Dijkstra)
    guia_puntos: tuple = ()                    # sus puntos de paso por cada frontera
    crisis: bool = False                       # la noticia activa es una crisis: senal sobre su lugar
    depuracion: bool = False                   # F3
    abiertas: frozenset | None = None          # zonas que son vertices del grafo (las demas estan en obras)
    zonas_crisis: frozenset = frozenset()
    aisladas: frozenset = frozenset()
    noche: bool = False                        # variante del mapa (Dia de eleccion)
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


def camara(mundo: MapaAbierto, ancho: int = ANCHO, alto: int = ALTO,
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


def _vista(mundo: MapaAbierto, cam: tuple[float, float], pantalla: pygame.Surface, margen: float = 90):
    """Funcion que dice si un punto del mundo cae en pantalla."""
    ancho, alto = pantalla.get_size()
    x0, y0, x1, y1 = cam[0] - margen, cam[1] - margen, cam[0] + ancho / ESCALA + margen, cam[1] + alto / ESCALA + margen
    return lambda x, y: x0 <= x <= x1 and y0 <= y <= y1


_CACHE: dict[str, pygame.Surface] = {}


def _capa(ruta, alfa: bool = False) -> pygame.Surface:
    """Una capa del mapa ya escalada a la pantalla: se carga y se escala una sola vez."""
    clave = f"{ruta}:{alfa}:{ESCALA}"
    if clave not in _CACHE:
        img = pygame.image.load(str(ruta))
        img = img.convert_alpha() if alfa else img.convert()
        _CACHE[clave] = pygame.transform.smoothscale(img, (px(img.get_width()), px(img.get_height())))
    return _CACHE[clave]


def _depuracion(pantalla: pygame.Surface, fuentes: Fuentes, mundo: MapaAbierto, cam: tuple[float, float]) -> None:
    """F3: zonas en color, colisiones en rojo, fronteras (verde abierta / roja cerrada) y aristas del grafo."""
    area = pygame.Rect(px(cam[0]), px(cam[1]), *pantalla.get_size())
    clave = f"depuracion:{ESCALA}"
    if clave not in _CACHE:
        zonas = _capa(mundo.imagenes["zonas"]).copy()
        zonas.set_alpha(80)
        colis = mundo.mascara.to_surface(setcolor=(255, 0, 0, 110), unsetcolor=(0, 0, 0, 0))
        _CACHE[clave] = zonas
        _CACHE[clave + ":colis"] = pygame.transform.scale(colis, (px(mundo.tamano[0]), px(mundo.tamano[1])))
    pantalla.blit(_CACHE[clave], (0, 0), area)
    pantalla.blit(_CACHE[clave + ":colis"], (0, 0), area)
    for f in mundo.fronteras:
        color = (220, 40, 40) if f.clave in mundo.cerradas else (40, 220, 90)
        x, y, w, h = f.calle
        pygame.draw.rect(pantalla, color, (*a_pantalla((x, y), cam), px(w), px(h)), px(3))
        for z in (f.desde, f.hasta):
            pygame.draw.line(pantalla, color, a_pantalla(mundo.zonas[z].centro, cam), a_pantalla(f.paso, cam), px(3))
    for z in mundo.zonas.values():
        pygame.draw.circle(pantalla, (255, 255, 255), a_pantalla(z.centro, cam), px(8))
    pygame.draw.rect(pantalla, (255, 255, 0), [*a_pantalla(mundo.rect_pies(mundo.jugador).topleft, cam),
                                               px(mundo.pies[0]), px(mundo.pies[1])], 1)
    img = fuentes.chica.render(f"F3 depuracion | zona: {mundo.zona_en(mundo.jugador)} | "
                               f"pos: {round(mundo.jugador[0])}, {round(mundo.jugador[1])}", True, (255, 255, 0))
    pantalla.blit(img, (px(16), pantalla.get_height() - px(150)))


def _franjas(capa: pygame.Surface, color: tuple, paso: int) -> None:
    """Rayado diagonal: el estado se lee por la forma, no solo por el color."""
    w, h = capa.get_size()
    for k in range(-h, w, paso):
        pygame.draw.line(capa, color, (k, h), (k + h, 0), px(5))


def _estados_de_zona(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MapaAbierto,
                     cam: tuple[float, float], estado: EstadoMundo) -> None:
    """Superposiciones alineadas con la region de cada zona: obras (aun no es vertice), crisis o aislada."""
    for z in mundo.zonas.values():
        if estado.abiertas is not None and z.id not in estado.abiertas:
            fondo, rayas, texto = (*tema.fondo, 150), (*tema.detalle, 140), "En obras"
        elif z.id in estado.zonas_crisis:
            fondo, rayas = (*tema.malo, 45), (*tema.malo, 90)
            texto = "En crisis y aislada" if z.id in estado.aisladas else "Zona en crisis"
        elif z.id in estado.aisladas:
            fondo, rayas, texto = (*tema.fondo, 120), (*tema.texto_off, 70), "Aislada: sin desmentidos"
        else:
            continue
        x, y, w, h = z.rect
        rect = pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h))
        if not rect.colliderect(pantalla.get_rect()):
            continue
        capa = pygame.Surface(rect.size, pygame.SRCALPHA)
        capa.fill(fondo)
        _franjas(capa, rayas, px(46))
        pantalla.blit(capa, rect)
        img = fuentes.normal.render(texto, True, tema.texto)
        caja = img.get_rect(center=a_pantalla(z.centro, cam)).inflate(px(16), px(8))
        pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(8))
        pantalla.blit(img, img.get_rect(center=caja.center))


def _barrera(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect) -> None:
    """Valla de obra con franjas: la arista que el grafo cerro, hecha objeto."""
    pygame.draw.rect(pantalla, tema.fondo, rect.inflate(px(4), px(4)), border_radius=px(4))
    pygame.draw.rect(pantalla, tema.detalle, rect, border_radius=px(4))
    paso = px(16)
    horizontal = rect.w >= rect.h
    for k in range(0, (rect.w if horizontal else rect.h), paso * 2):
        franja = (pygame.Rect(rect.x + k, rect.y, paso, rect.h) if horizontal
                  else pygame.Rect(rect.x, rect.y + k, rect.w, paso)).clip(rect)
        pygame.draw.rect(pantalla, tema.malo, franja)


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MapaAbierto,
                  estado: EstadoMundo | None = None, arte: ArteFormas = ARTE_FORMAS) -> None:
    estado = estado or EstadoMundo()
    cam = camara(mundo, *pantalla.get_size(), estado.centro_camara)
    pantalla.fill(tema.suelo)
    fondo = mundo.imagenes["noche" if estado.noche and "noche" in mundo.imagenes else "mapa"]
    pantalla.blit(_capa(fondo), (0, 0), pygame.Rect(px(cam[0]), px(cam[1]), *pantalla.get_size()))
    _estados_de_zona(pantalla, fuentes, tema, mundo, cam, estado)
    deco = estado.decorado
    visible = _vista(mundo, cam, pantalla)
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
    for f in mundo.barreras_activas():
        x, y, w, h = f.barrera
        _barrera(pantalla, tema, pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h)))
    if estado.guia_puntos:
        _guia(pantalla, tema, cam, (mundo.jugador, *estado.guia_puntos))
    resaltada = estado.accion[0] if estado.accion else None
    for z in mundo.zonas.values():
        x, y, w, h = z.edificio
        rect = pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h))
        if not rect.colliderect(pantalla.get_rect()):
            continue
        if z.id == resaltada:
            pygame.draw.rect(pantalla, tema.acento, rect.inflate(px(10), px(10)), px(5), border_radius=px(14))
        if z.id == estado.noticia:
            if estado.crisis:   # senal de crisis: anillo que late alrededor del lugar
                radio = px(60) + round(px(14) * (0.5 + 0.5 * math.sin(estado.t * 6)))
                pygame.draw.circle(pantalla, tema.malo, a_pantalla(z.centro, cam), radio, px(6))
            _globo_noticia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(8)))
        elif z.id in estado.evidencias:
            _marca_evidencia(pantalla, tema, fuentes, (rect.centerx, rect.top - px(26)))
    if deco is not None:
        for x, y, tam, fase in deco.arboles:
            if visible(x, y):
                arte.arbol(pantalla, tema, a_pantalla((x, y), cam), px(34 * tam), math.sin(estado.t * 1.3 + fase))
    x, y = mundo.jugador
    arte.personaje(pantalla, tema, a_pantalla((x, y + mundo.pies[1] / 2), cam), px(ALTO_PERSONAJE * 14),
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
    if estado.depuracion:
        _depuracion(pantalla, fuentes, mundo, cam)
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


def _guia(pantalla: pygame.Surface, tema: Tema, cam: tuple[float, float], puntos: tuple) -> None:
    """Ruta tenue por los puntos de paso de cada frontera: puntos espaciados, no una linea solida."""
    capa = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    color = (*tema.acento, 150)
    for a, b in zip(puntos, puntos[1:]):
        (x1, y1), (x2, y2) = a_pantalla(a, cam), a_pantalla(b, cam)
        largo = max(1, round(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / px(26)))
        for i in range(largo + 1):
            pygame.draw.circle(capa, color, (x1 + (x2 - x1) * i // largo, y1 + (y2 - y1) * i // largo), px(6))
    pantalla.blit(capa, (0, 0))


def _minimapa(pantalla: pygame.Surface, tema: Tema, mundo: MapaAbierto, estado: EstadoMundo) -> None:
    """Toda la ciudad en pequeno: zonas, fronteras abiertas, la noticia, la evidencia y el jugador."""
    r = RECT_MINIMAPA
    pygame.draw.rect(pantalla, tema.panel, r, border_radius=px(10))
    pygame.draw.rect(pantalla, tema.borde, r, px(2), border_radius=px(10))
    interior = r.inflate(-px(20), -px(20))
    ancho, alto = mundo.tamano

    def m(p: tuple[float, float]) -> tuple[int, int]:
        return interior.x + round(p[0] / ancho * interior.w), interior.y + round(p[1] / alto * interior.h)
    for f in mundo.fronteras:
        if f.clave not in mundo.cerradas:
            pygame.draw.lines(pantalla, tema.borde, False,
                              [m(mundo.zonas[f.desde].centro), m(f.paso), m(mundo.zonas[f.hasta].centro)], px(3))
    for z in mundo.zonas.values():
        if estado.abiertas is None or z.id in estado.abiertas:
            color = tema.malo if z.id in estado.zonas_crisis else tema.texto_off if z.id in estado.aisladas else tema.borde
            pygame.draw.circle(pantalla, color, m(z.centro), px(5))
    if estado.noticia in mundo.zonas:
        caja = pygame.Rect(0, 0, px(12), px(12))
        caja.center = m(mundo.zonas[estado.noticia].centro)
        pygame.draw.rect(pantalla, tema.texto, caja.inflate(px(4), px(4)))
        pygame.draw.rect(pantalla, tema.malo, caja)
    for z in estado.evidencias:
        if z in mundo.zonas:
            _rombo(pantalla, tema.detalle, m(mundo.zonas[z].centro), px(6), True)
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
