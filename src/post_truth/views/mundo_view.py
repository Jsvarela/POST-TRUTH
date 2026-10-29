"""Vista del mundo caminable."""
import math
from dataclasses import dataclass, field

import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models import Role
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.arte_mundo import ARTE_PIXEL, ArteFormas
from post_truth.views.decorado import Decorado
from post_truth.views.componentes import Fuentes, ajustar_texto, panel
from post_truth.views.escena_view import dibujar_reloj
from post_truth.views.hud import PLACA
from post_truth.views.mapa_view import _rombo
from post_truth.views.theme import TEMAS, TOKENS, Tema, esp

AYUDA = "WASD: caminar   |   E: entrar al lugar   |   G: guia   |   H: habilidad   |   Y: aliados   |   F3   |   ESC: menu"
ALTO_PERSONAJE = 3.2
PAJAROS = ((260, 70, 0.0), (300, 70, 0.6), (1100, -55, 9.0))
RECT_MINIMAPA = pygame.Rect(ANCHO - px(16) - px(220), px(16), px(220), px(138))


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
    salud: float = 0.0                         # -1 ciudad enferma .. 1 sana: tine el mapa
    aviso: str = ""
    personaje: Personaje = Personaje(Role.CITIZEN, Genero.MUJER)
    centro_camara: tuple[float, float] | None = None
    decorado: Decorado | None = None
    t: float = 0.0
    reloj: tuple[float, float] | None = None   # (restante, total) del reloj de una publicacion viral
    dia: tuple[int, int] | None = None         # (dia, total) de la campana
    fraccion_dia: float = 0.0                  # 0 amanecer .. 1 noche
    credibilidad: int | None = None
    texto_accion: str = ""                     # que hace E aqui, cuando hay una sola opcion
    animacion: AnimacionPersonaje = field(default_factory=AnimacionPersonaje)
    otros: tuple = ()   # multijugador: (nombre, personaje, posicion, animacion, cuadro, conectado) de los demas
    transeuntes: tuple = ()   # (nombre, personaje, posicion, animacion, cuadro, marca: rumor/testigo/enojado/"")
    charla: tuple | None = None   # (posicion, progreso 0..1, lo que dice el, tu argumento)


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


def _tinte_de_salud(pantalla: pygame.Surface, tema: Tema, salud: float) -> None:
    """La ciudad se ve como esta: gris y fria si empeora, calida si mejora (colores del tema)."""
    if abs(salud) < 0.05:
        return
    capa = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    capa.fill((*tema.fondo, round(80 * -salud)) if salud < 0 else (*tema.detalle, round(30 * salud)))
    pantalla.blit(capa, (0, 0))


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
        # pixel art: se amplia sin suavizar para que los pixeles queden nitidos
        _CACHE[clave] = pygame.transform.scale(img, (px(img.get_width()), px(img.get_height())))
    return _CACHE[clave]


def _depuracion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MapaAbierto,
                cam: tuple[float, float]) -> None:
    """F3: zonas en color, colisiones en rojo, fronteras (verde abierta / roja cerrada) y aristas del grafo."""
    area = pygame.Rect(px(cam[0]), px(cam[1]), *pantalla.get_size())
    clave = f"depuracion:{ESCALA}:{id(tema)}"
    if clave not in _CACHE:
        zonas = _capa(mundo.imagenes["zonas"]).copy()
        zonas.set_alpha(80)
        colis = mundo.mascara.to_surface(setcolor=(*tema.malo, 110), unsetcolor=(*tema.fondo, 0))
        _CACHE[clave] = zonas
        _CACHE[clave + ":colis"] = pygame.transform.scale(colis, (px(mundo.tamano[0]), px(mundo.tamano[1])))
    pantalla.blit(_CACHE[clave], (0, 0), area)
    pantalla.blit(_CACHE[clave + ":colis"], (0, 0), area)
    for f in mundo.fronteras:
        color = tema.malo if f.clave in mundo.cerradas else tema.bueno
        x, y, w, h = f.calle
        pygame.draw.rect(pantalla, color, (*a_pantalla((x, y), cam), px(w), px(h)), px(3))
        for z in (f.desde, f.hasta):
            pygame.draw.line(pantalla, color, a_pantalla(mundo.zonas[z].centro, cam), a_pantalla(f.paso, cam), px(3))
    for z in mundo.zonas.values():
        pygame.draw.circle(pantalla, tema.texto, a_pantalla(z.centro, cam), px(8))
    pygame.draw.rect(pantalla, tema.detalle, [*a_pantalla(mundo.rect_pies(mundo.jugador).topleft, cam),
                                               px(mundo.pies[0]), px(mundo.pies[1])], 1)
    img = fuentes.chica.render(f"F3 depuracion | zona: {mundo.zona_en(mundo.jugador)} | "
                               f"pos: {round(mundo.jugador[0])}, {round(mundo.jugador[1])}", True, tema.detalle)
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
        pygame.draw.rect(pantalla, tema.panel, caja)
        pantalla.blit(img, img.get_rect(center=caja.center))


def _barrera(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect) -> None:
    """Valla de obra con franjas: la arista que el grafo cerro, hecha objeto."""
    pygame.draw.rect(pantalla, tema.fondo, rect.inflate(px(4), px(4)))
    pygame.draw.rect(pantalla, tema.detalle, rect)
    paso = px(16)
    horizontal = rect.w >= rect.h
    for k in range(0, (rect.w if horizontal else rect.h), paso * 2):
        franja = (pygame.Rect(rect.x + k, rect.y, paso, rect.h) if horizontal
                  else pygame.Rect(rect.x, rect.y + k, rect.w, paso)).clip(rect)
        pygame.draw.rect(pantalla, tema.malo, franja)


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MapaAbierto,
                  estado: EstadoMundo | None = None, arte: ArteFormas = ARTE_PIXEL) -> None:
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
            pygame.draw.rect(pantalla, tema.acento, rect.inflate(px(10), px(10)), px(5))
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
    alto = px(ALTO_PERSONAJE * 14)
    for nombre, personaje, (tx, ty), animacion, cuadro, marca in estado.transeuntes:
        if visible(tx, ty):
            pies = a_pantalla((tx, ty + mundo.pies[1] / 2), cam)
            arte.personaje(pantalla, tema, pies, alto, personaje, animacion, cuadro)
            if marca:
                _marca_transeunte(pantalla, tema, marca, (pies[0], pies[1] - alto - px(14)))
    if estado.charla is not None:
        (cx, cy), lleno, _, _ = estado.charla
        caja = pygame.Rect(0, 0, px(64), px(64))
        caja.center = a_pantalla((cx, cy - mundo.pies[1]), cam)
        pygame.draw.arc(pantalla, tema.bueno, caja, math.pi / 2, math.pi / 2 + 2 * math.pi * max(0.02, lleno), px(6))
    for nombre, personaje, (ox, oy), animacion, cuadro, conectado in estado.otros:   # los demas, debajo del propio
        if visible(ox, oy):
            pies = a_pantalla((ox, oy + mundo.pies[1] / 2), cam)
            arte.personaje(pantalla, tema, pies, alto, personaje, animacion, cuadro)
            _etiqueta(pantalla, fuentes, tema, nombre, (pies[0], pies[1] - alto - px(4)), conectado)
    x, y = mundo.jugador
    arte.personaje(pantalla, tema, a_pantalla((x, y + mundo.pies[1] / 2), cam), alto,
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
    _tinte_de_salud(pantalla, tema, estado.salud)
    if estado.depuracion:
        _depuracion(pantalla, fuentes, tema, mundo, cam)
    _minimapa(pantalla, tema, mundo, estado)   # la placa de indicadores la pone la capa global (views/efectos.py)
    if estado.reloj is not None:
        dibujar_reloj(pantalla, fuentes, tema, *estado.reloj, (PLACA.x, PLACA.bottom + px(10)))
    _franja(pantalla, fuentes, tema, _mensaje(estado))


def _marca_transeunte(pantalla: pygame.Surface, tema: Tema, marca: str, c: tuple[int, int]) -> None:
    """Sobre la cabeza, por forma: triangulo con rumor, circulo testigo, cuadrado enojado."""
    x, y = c
    r = px(10)
    if marca == "rumor":
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - r), (x + r, y + r), (x - r, y + r)])
        pygame.draw.line(pantalla, tema.fondo, (x, y - r // 3), (x, y + r // 2), px(2))
    elif marca == "testigo":
        pygame.draw.circle(pantalla, tema.bueno, c, r)
        pygame.draw.circle(pantalla, tema.fondo, c, r // 3)
    else:
        pygame.draw.rect(pantalla, tema.detalle, (x - r, y - r, 2 * r, 2 * r))


def _etiqueta(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, texto: str, punta: tuple[int, int],
              activo: bool) -> None:
    """Nombre de otro jugador sobre su cabeza (apagado si se desconecto)."""
    img = fuentes.chica.render(texto, True, tema.texto if activo else tema.texto_off)
    rect = img.get_rect(midbottom=punta).inflate(esp(2), px(4))
    pygame.draw.rect(pantalla, tema.panel, rect)
    pygame.draw.rect(pantalla, tema.acento if activo else tema.borde, rect, width=px(2))
    pantalla.blit(img, img.get_rect(center=rect.center))


def _globo_noticia(pantalla: pygame.Surface, tema: Tema, fuentes: Fuentes, punta: tuple[int, int]) -> None:
    """Globo de dialogo con "!": aqui ocurre la noticia activa."""
    x, y = punta
    caja = pygame.Rect(0, 0, px(46), px(40))
    caja.midbottom = (x, y - px(12))
    pygame.draw.polygon(pantalla, tema.texto, [(x - px(9), caja.bottom - px(2)), (x + px(9), caja.bottom - px(2)), (x, y)])
    pygame.draw.rect(pantalla, tema.texto, caja.inflate(px(6), px(6)))
    pygame.draw.rect(pantalla, tema.malo, caja)
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
    pygame.draw.rect(pantalla, tema.panel, r)
    pygame.draw.rect(pantalla, tema.borde, r, px(2))
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
    if estado.charla is not None:                       # lo que dice el transeunte y tu argumento
        return f"{estado.charla[2]}   {estado.charla[3]}".strip()
    if estado.aviso:
        return estado.aviso
    if estado.texto_accion.startswith("Manten E"):      # alguien de la calle al alcance
        return estado.texto_accion
    if estado.accion is not None:
        zona, que = estado.accion
        if que == "elegir":
            return f"E: ver que hacer en {zona.capitalize()}"
        return f"E: {estado.texto_accion[0].lower()}{estado.texto_accion[1:]}" if estado.texto_accion else ""
    if estado.guia:
        return f"Guia: la noticia esta en {estado.noticia.capitalize()}"
    return ""


def _franja(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mensaje: str) -> None:
    """Abajo: el mensaje del momento en una pildora flotante y la ayuda de teclas en una linea pequena."""
    ancho, alto = pantalla.get_size()
    ayuda = fuentes.chica.render(AYUDA, True, tema.texto)
    fondo = pygame.Rect(0, alto - ayuda.get_height() - esp(2), ancho, ayuda.get_height() + esp(2))
    capa = pygame.Surface(fondo.size, pygame.SRCALPHA)
    capa.fill((*tema.panel, TOKENS.alfa_panel))
    pantalla.blit(capa, fondo)
    pantalla.blit(ayuda, ayuda.get_rect(center=fondo.center))
    if not mensaje:
        return
    lineas = ajustar_texto(mensaje, fuentes.normal, ancho - px(240))[:2]
    w = max(fuentes.normal.size(l)[0] for l in lineas) + esp(5) * 2
    caja = pygame.Rect(0, 0, w, len(lineas) * fuentes.normal.get_linesize() + esp(3) * 2)
    caja.midbottom = (ancho // 2, fondo.y - esp(2))
    panel(pantalla, tema, caja, TOKENS.alfa_panel, borde=tema.acento)
    y = caja.y + esp(3)
    for linea in lineas:
        img = fuentes.normal.render(linea, True, tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(caja.centerx, y)))
        y += fuentes.normal.get_linesize()
