"""Telefono Civitas: la red social en vivo (estado de cada ciudadano por FORMA y color), la noticia viajando por las
aristas, las herramientas con su enfriamiento y las notificaciones. El jugador no ve pesos ni probabilidades."""
import math
from dataclasses import dataclass

import pygame

from post_truth.config import ANCHO, px
from post_truth.sesion import HERRAMIENTAS as NOMBRES
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion_vivo import (COMPARTIO, ENFRIAMIENTO, ENTERADO, INMUNE, SIN_ENTERARSE,
                                                    PropagacionEnVivo)
from post_truth.views.anuncio_view import _icono
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.grafo_view import _equis
from post_truth.views.theme import Tema

PESTANAS = ("Red", "Notificaciones", "Publicar")
HERRAMIENTAS = tuple(NOMBRES)   # en el orden de las teclas 1-4
RADIO = px(11)
SUBIDA = 0.25   # segundos que tarda el telefono en subir

TELEFONO = pygame.Rect(ANCHO // 2 - px(235), px(42), px(470), px(590))
CERRAR = pygame.Rect(TELEFONO.right - px(46), TELEFONO.y + px(12), px(30), px(30))
AREA_RED = pygame.Rect(TELEFONO.x + px(24), TELEFONO.y + px(126), TELEFONO.w - px(48), px(236))


def rect_pestana(i: int) -> pygame.Rect:
    ancho = (TELEFONO.w - px(36)) // len(PESTANAS)
    return pygame.Rect(TELEFONO.x + px(18) + i * ancho, TELEFONO.y + px(52), ancho - px(4), px(34))


def rect_herramienta(i: int) -> pygame.Rect:
    ancho = (TELEFONO.w - px(52)) // 2
    return pygame.Rect(TELEFONO.x + px(18) + (i % 2) * (ancho + px(16)), TELEFONO.y + px(420) + (i // 2) * px(64),
                       ancho, px(56))


def posiciones(grafo: GrafoSocial) -> dict[str, tuple[int, int]]:
    return {c.id: (round(AREA_RED.x + c.pos[0] * AREA_RED.w), round(AREA_RED.y + c.pos[1] * AREA_RED.h))
            for c in grafo.vertices()}


def ciudadano_en(grafo: GrafoSocial, punto: tuple[int, int]) -> str | None:
    """El ciudadano bajo el raton (con un margen para que sea facil atinarle)."""
    for id, p in posiciones(grafo).items():
        if math.dist(p, punto) <= RADIO * 1.6:
            return id
    return None


@dataclass
class VistaTelefono:
    grafo: GrafoSocial
    en_vivo: PropagacionEnVivo | None
    pestana: int
    seleccionado: str
    notificaciones: list[dict]
    leidas: int
    reloj: tuple[float, float] | None   # (restante, total) de la crisis
    extendido: bool
    alerta: float                       # segundos que quedan del destello de "se volvio viral"
    t: float


def dibujar_telefono(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    velo.fill((*tema.fondo, 150))
    pantalla.blit(velo, (0, 0))
    subida = min(1.0, v.t / SUBIDA)
    dy = round((1 - (1 - (1 - subida) ** 3)) * (pantalla.get_height() - TELEFONO.y))   # sube y frena (ease-out)
    sup = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    _marco(sup, fuentes, tema, v)
    if v.pestana == 0:
        _red(sup, fuentes, tema, v)
    elif v.pestana == 1:
        _notificaciones(sup, fuentes, tema, v)
    else:
        _texto_centrado(sup, fuentes, tema, "Muy pronto: arma tus propias publicaciones y mira como viajan.")
    pantalla.blit(sup, (0, dy))


def _marco(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    pygame.draw.rect(sup, tema.panel, TELEFONO, border_radius=px(28))
    destello = v.alerta > 0 and math.sin(v.t * 12) > 0   # se volvio viral: el borde parpadea
    pygame.draw.rect(sup, tema.malo if destello else tema.borde, TELEFONO, px(6 if destello else 4),
                     border_radius=px(28))
    sup.blit(fuentes.grande.render("Civitas", True, tema.acento), (TELEFONO.x + px(22), TELEFONO.y + px(10)))
    if v.reloj is not None:
        restante, total = v.reloj
        color = tema.malo if restante < total * 0.35 else tema.texto
        texto = f"Crisis: {math.ceil(restante)} s"
    else:
        color, texto = tema.texto, ""
    texto += ("   " if texto else "") + ("Tiempo x0.25 (extendido)" if v.extendido else "Tiempo x0.25")
    img = fuentes.chica.render(texto, True, color)
    sup.blit(img, img.get_rect(midright=(CERRAR.x - px(10), CERRAR.centery)))
    pygame.draw.rect(sup, tema.boton, CERRAR, border_radius=px(8))
    _equis(sup, tema.boton_texto, CERRAR.center, px(6))
    for i, nombre in enumerate(PESTANAS):
        r = rect_pestana(i)
        activa = i == v.pestana
        pygame.draw.rect(sup, tema.boton if activa else tema.fondo, r, border_radius=px(8))
        pygame.draw.rect(sup, tema.acento if activa else tema.borde, r, px(2), border_radius=px(8))
        sin_leer = len(v.notificaciones) - v.leidas
        etiqueta = f"{nombre} ({sin_leer})" if i == 1 and sin_leer > 0 else nombre
        img = fuentes.chica.render(etiqueta, True, tema.boton_texto if activa else tema.texto)
        sup.blit(img, img.get_rect(center=r.center))
    ayuda = "1-4: herramientas   Flechas: elegir   Tab: pestana   T: cerrar"
    img = fuentes.chica.render(ayuda, True, tema.texto_off)
    sup.blit(img, img.get_rect(midbottom=(TELEFONO.centerx, TELEFONO.bottom - px(10))))


def _red(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    p, pos = v.en_vivo, posiciones(v.grafo)
    if p is None:
        resumen = "La red esta en calma: no hay rumores corriendo."
    else:
        resumen = (f"La creen {p.creen}   |   Inmunes {p.contar(INMUNE)}   |   "
                   f"Sin enterarse {p.contar(SIN_ENTERARSE)}")
    sup.blit(fuentes.chica.render(resumen, True, tema.texto), (TELEFONO.x + px(22), TELEFONO.y + px(96)))
    for a in v.grafo.aristas():
        pygame.draw.line(sup, tema.borde, pos[a.origen], pos[a.destino], max(1, round(px(3) * a.peso)))
    if p is not None:   # la noticia viajando: rumor = circulo, desmentido = cuadrado
        avance = p.progreso_paso
        for frente, destinos, desmentido in ((p.rumor, (SIN_ENTERARSE,), False),
                                             (p.desmentido, (SIN_ENTERARSE, ENTERADO), True)):
            for u in frente:
                for a in v.grafo.vecinos(u):
                    if p.estado[a.destino] in destinos:
                        x0, y0 = pos[u]
                        x1, y1 = pos[a.destino]
                        punto = (round(x0 + (x1 - x0) * avance), round(y0 + (y1 - y0) * avance))
                        if desmentido:
                            pygame.draw.rect(sup, tema.bueno, pygame.Rect(0, 0, px(8), px(8)).move(
                                punto[0] - px(4), punto[1] - px(4)))
                        else:
                            pygame.draw.circle(sup, tema.malo, punto, px(4))
    for c in v.grafo.vertices():
        estado = p.estado[c.id] if p is not None else SIN_ENTERARSE
        activo = p is not None and (c.id in p.rumor or c.id in p.desmentido)
        _nodo(sup, tema, pos[c.id], estado, activo, v.t)
        if p is not None and c.id in p.limitadas:
            _equis(sup, tema.acento, (pos[c.id][0] + RADIO, pos[c.id][1] - RADIO), px(4))
        if c.id == v.seleccionado:
            pygame.draw.circle(sup, tema.acento, pos[c.id], RADIO + px(6), px(2))
    _leyenda(sup, fuentes, tema)
    nombre = v.grafo.vertice(v.seleccionado).nombre
    sup.blit(fuentes.chica.render(f"Elegido: {nombre}", True, tema.acento), (TELEFONO.x + px(22), TELEFONO.y + px(394)))
    for i, accion in enumerate(HERRAMIENTAS):
        _herramienta(sup, fuentes, tema, i, accion, p)


def _nodo(sup: pygame.Surface, tema: Tema, centro: tuple[int, int], estado: str, activo: bool, t: float) -> None:
    """Forma por estado (se distingue sin color): circulo vacio, circulo lleno, triangulo, cuadrado."""
    x, y = centro
    r = RADIO
    if activo:   # sigue difundiendo: late
        pygame.draw.circle(sup, tema.texto, centro, r + px(3) + round(px(2) * math.sin(t * 6)), 1)
    if estado == SIN_ENTERARSE:
        pygame.draw.circle(sup, tema.fondo, centro, r)
        pygame.draw.circle(sup, tema.texto_off, centro, r, px(2))
    elif estado == ENTERADO:
        pygame.draw.circle(sup, tema.malo, centro, r)
    elif estado == COMPARTIO:
        pygame.draw.polygon(sup, tema.malo, [(x, y - r - px(2)), (x + r + px(1), y + r), (x - r - px(1), y + r)])
    else:
        pygame.draw.rect(sup, tema.bueno, pygame.Rect(x - r, y - r, 2 * r, 2 * r), border_radius=px(3))


def _leyenda(sup: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
    x, y = TELEFONO.x + px(30), TELEFONO.y + px(372)
    for estado, texto in ((SIN_ENTERARSE, "No sabe"), (ENTERADO, "La cree"), (COMPARTIO, "La comparte"),
                          (INMUNE, "Inmune")):
        _nodo(sup, tema, (x, y + px(8)), estado, False, 0)
        img = fuentes.chica.render(texto, True, tema.texto)
        sup.blit(img, (x + RADIO + px(6), y))
        x += RADIO + img.get_width() + px(26)


def _herramienta(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, i: int, accion: str,
                 p: PropagacionEnVivo | None) -> None:
    r = rect_herramienta(i)
    falta = p.enfriando[accion] if p is not None else 0.0
    lista = p is not None and falta == 0
    pygame.draw.rect(sup, tema.boton if lista else tema.boton_off, r, border_radius=px(10))
    if p is not None and falta > 0:   # la barra se llena mientras recarga
        lleno = r.w * (1 - falta / ENFRIAMIENTO[accion])
        pygame.draw.rect(sup, tema.boton, pygame.Rect(r.x, r.y, round(lleno), r.h), border_radius=px(10))
    pygame.draw.rect(sup, tema.acento if lista else tema.texto_off, r, px(2), border_radius=px(10))
    color = tema.boton_texto if lista else tema.texto_off
    sup.blit(fuentes.normal.render(f"{i + 1}. {NOMBRES[accion]}", True, color), (r.x + px(12), r.y + px(5)))
    estado = "Lista" if lista else f"Recargando {math.ceil(falta)} s" if p is not None else "Sin rumor"
    sup.blit(fuentes.chica.render(estado, True, color), (r.x + px(12), r.y + px(32)))


def _notificaciones(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    if not v.notificaciones:
        _texto_centrado(sup, fuentes, tema, "Sin notificaciones por ahora.")
        return
    y = TELEFONO.y + px(100)
    for i in range(len(v.notificaciones) - 1, -1, -1):   # la mas nueva arriba
        n = v.notificaciones[i]
        caja = pygame.Rect(TELEFONO.x + px(18), y, TELEFONO.w - px(36), px(62))
        if caja.bottom > TELEFONO.bottom - px(34):
            break
        nueva = i >= v.leidas
        pygame.draw.rect(sup, tema.fondo, caja, border_radius=px(10))
        pygame.draw.rect(sup, tema.acento if nueva else tema.borde, caja, px(2), border_radius=px(10))
        _icono(sup, tema, n["tipo"], (caja.x + px(26), caja.centery), px(14), 0)
        sup.blit(fuentes.normal.render(n["titulo"], True, tema.texto), (caja.x + px(50), caja.y + px(6)))
        linea = ajustar_texto(n["texto"], fuentes.chica, caja.w - px(62))[0]
        sup.blit(fuentes.chica.render(linea, True, tema.texto), (caja.x + px(50), caja.y + px(34)))
        y += caja.h + px(8)


def _texto_centrado(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, texto: str) -> None:
    y = TELEFONO.y + px(200)
    for linea in ajustar_texto(texto, fuentes.normal, TELEFONO.w - px(80)):
        img = fuentes.normal.render(linea, True, tema.texto_off)
        sup.blit(img, img.get_rect(midtop=(TELEFONO.centerx, y)))
        y += fuentes.normal.get_linesize()


def dibujar_icono(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect, sin_leer: int,
                  alerta: float, t: float) -> None:
    """Telefono en el HUD del mundo: con globo de no leidas y un latido cuando algo se vuelve viral."""
    late = alerta > 0 and math.sin(t * 12) > 0
    pygame.draw.rect(pantalla, tema.panel, rect, border_radius=px(10))
    pygame.draw.rect(pantalla, tema.malo if late else tema.borde, rect, px(4 if late else 2), border_radius=px(10))
    cuerpo = pygame.Rect(0, 0, px(18), px(28))
    cuerpo.center = (rect.x + px(22), rect.centery)
    pygame.draw.rect(pantalla, tema.texto, cuerpo, px(2), border_radius=px(4))
    pygame.draw.circle(pantalla, tema.texto, (cuerpo.centerx, cuerpo.bottom - px(5)), px(2))
    img = fuentes.chica.render("T: telefono", True, tema.texto)
    pantalla.blit(img, img.get_rect(midleft=(cuerpo.right + px(8), rect.centery)))
    if sin_leer:
        globo = (rect.right - px(4), rect.y + px(4))
        pygame.draw.circle(pantalla, tema.malo, globo, px(11))
        n = fuentes.chica.render(str(min(sin_leer, 9)), True, tema.fondo)
        pantalla.blit(n, n.get_rect(center=globo))
