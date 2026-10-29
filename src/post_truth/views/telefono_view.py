"""Telefono Civitas: la red social en vivo (estado de cada ciudadano por FORMA y color), la noticia viajando por las
aristas, las herramientas con su enfriamiento y las notificaciones. El jugador no ve pesos ni probabilidades."""
import math
from dataclasses import dataclass

import pygame

from post_truth.config import ANCHO, px
from post_truth.models.posts import Evaluacion
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion_vivo import (COMPARTIO, ENFRIAMIENTO, ENTERADO, INMUNE, SIN_ENTERARSE,
                                                    RADIO_ESCUDO, RADIO_ONDA, PropagacionEnVivo)
from post_truth.views.anuncio_view import _icono
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.grafo_view import _equis
from post_truth.views.theme import Tema, mezclar

PESTANAS = ("Red", "Notificaciones", "Publicar")
ONDA = 0.6            # segundos que dura la animacion de la onda
RADIO = px(11)
SUBIDA = 0.25   # segundos que tarda el telefono en subir
PULSO = 0.8     # segundos que dura el anillo de un ciudadano al que le acaba de llegar la noticia

TELEFONO = pygame.Rect(ANCHO // 2 - px(235), px(30), px(470), px(596))
CERRAR = pygame.Rect(TELEFONO.right - px(46), TELEFONO.y + px(12), px(30), px(30))
AREA_RED = pygame.Rect(TELEFONO.x + px(24), TELEFONO.y + px(126), TELEFONO.w - px(48), px(236))


def rect_pestana(i: int) -> pygame.Rect:
    ancho = (TELEFONO.w - px(36)) // len(PESTANAS)
    return pygame.Rect(TELEFONO.x + px(18) + i * ancho, TELEFONO.y + px(52), ancho - px(4), px(34))


def rect_fila(i: int) -> pygame.Rect:
    """Fila de una pieza del post en la pestana Publicar."""
    return pygame.Rect(TELEFONO.x + px(18), TELEFONO.y + px(98) + i * px(46), TELEFONO.w - px(36), px(40))


RECT_PUBLICAR = pygame.Rect(TELEFONO.x + px(18), TELEFONO.y + px(468), TELEFONO.w - px(36), px(50))


def posiciones(grafo: GrafoSocial) -> dict[str, tuple[int, int]]:
    return {c.id: (round(AREA_RED.x + c.pos[0] * AREA_RED.w), round(AREA_RED.y + c.pos[1] * AREA_RED.h))
            for c in grafo.vertices()}


@dataclass
class VistaPublicar:
    filas: list[tuple[str, str]]   # (pieza, opcion elegida)
    fila: int
    evaluacion: Evaluacion
    enfriamiento: float
    enfriamiento_total: float
    en_curso: bool                 # ya hay un post tuyo corriendo


@dataclass
class VistaTelefono:
    grafo: GrafoSocial
    en_vivo: PropagacionEnVivo | None
    pestana: int
    escudo: tuple[float, float]         # posicion normalizada del escudo sobre la red
    notificaciones: list[dict]
    leidas: int
    reloj: tuple[float, float] | None   # (restante, total) de la crisis
    extendido: bool
    alerta: float                       # segundos que quedan del destello de "se volvio viral"
    t: float
    publicar: VistaPublicar | None = None
    pulsos: dict[str, float] | None = None   # ciudadano -> segundos desde que le llego algo (anillo que crece)
    hora: float = 0.0                         # fraccion del dia (la hora de la barra de estado)
    ondas: tuple = ()                         # (centro normalizado, edad) de los desmentidos en onda
    atajo: float = 0.0                        # destello del escudo cuando acaba de atajar un rumor


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
    elif v.publicar is not None:
        _publicar(sup, fuentes, tema, v.publicar)
    pantalla.blit(sup, (0, dy))


def _marco(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    # carcasa del celular: cuerpo, pantalla con borde interior, muesca y barra de inicio
    carcasa = TELEFONO.inflate(px(14), px(14))
    pygame.draw.rect(sup, mezclar(tema.fondo, tema.borde, 0.35), carcasa)
    pygame.draw.rect(sup, tema.panel, TELEFONO)
    destello = v.alerta > 0 and math.sin(v.t * 12) > 0   # se volvio viral: el borde parpadea
    pygame.draw.rect(sup, tema.malo if destello else tema.borde, TELEFONO, px(6 if destello else 3))
    muesca = pygame.Rect(0, 0, px(110), px(16))
    muesca.midtop = (TELEFONO.centerx, carcasa.y + px(2))
    pygame.draw.rect(sup, mezclar(tema.fondo, tema.borde, 0.35), muesca)
    pygame.draw.rect(sup, tema.texto_off, (TELEFONO.centerx - px(50), TELEFONO.bottom + px(1), px(100), px(4)))
    horas = 6 + v.hora * 16   # el dia va de 6:00 a 22:00
    estado = fuentes.chica.render(f"{int(horas):02d}:{int(horas % 1 * 60):02d}", True, tema.texto)
    sup.blit(estado, (muesca.right + px(14), TELEFONO.y + px(1)))
    bateria = pygame.Rect(muesca.right + px(24) + estado.get_width(), TELEFONO.y + px(5), px(24), px(11))
    pygame.draw.rect(sup, tema.texto, bateria, 1)
    pygame.draw.rect(sup, tema.bueno, bateria.inflate(-px(4), -px(4)).move(0, 0))
    sup.blit(fuentes.grande.render("Civitas", True, tema.acento), (TELEFONO.x + px(22), TELEFONO.y + px(14)))
    x = CERRAR.x - px(10)
    if v.reloj is not None:   # crisis: cuenta regresiva grande en un anillo que se vacia
        restante, total = v.reloj
        color = tema.malo if restante < total * 0.35 else tema.acento
        centro = (x - px(20), CERRAR.centery + px(6))
        anillo = pygame.Rect(0, 0, px(40), px(40))
        anillo.center = centro
        pygame.draw.circle(sup, tema.fondo, centro, px(20))
        fraccion = max(0.0, min(1.0, restante / total)) if total else 0.0
        if fraccion > 0:
            pygame.draw.arc(sup, color, anillo, math.pi / 2, math.pi / 2 + 2 * math.pi * fraccion, px(4))
        num = fuentes.grande.render(str(math.ceil(restante)), True, tema.texto)
        sup.blit(num, num.get_rect(center=centro))
        x -= px(48)
    img = fuentes.chica.render("x0.25 (ext.)" if v.extendido else "x0.25", True, tema.texto_off)
    sup.blit(img, img.get_rect(midright=(x, CERRAR.centery + px(6))))
    pygame.draw.rect(sup, tema.boton, CERRAR)
    _equis(sup, tema.boton_texto, CERRAR.center, px(6))
    for i, nombre in enumerate(PESTANAS):
        r = rect_pestana(i)
        activa = i == v.pestana
        pygame.draw.rect(sup, tema.boton if activa else tema.fondo, r)
        pygame.draw.rect(sup, tema.acento if activa else tema.borde, r, px(2))
        sin_leer = len(v.notificaciones) - v.leidas
        etiqueta = f"{nombre} ({sin_leer})" if i == 1 and sin_leer > 0 else nombre
        img = fuentes.chica.render(etiqueta, True, tema.boton_texto if activa else tema.texto)
        sup.blit(img, img.get_rect(center=r.center))
    ayuda = ("Flechas: armar   Enter: publicar   Tab: pestana   T: cerrar" if v.pestana == 2
             else "WASD, flechas o raton: escudo   Espacio: desmentido   Tab   T: cerrar")
    img = fuentes.chica.render(ayuda, True, tema.texto_off)
    sup.blit(img, img.get_rect(midbottom=(TELEFONO.centerx, TELEFONO.bottom - px(10))))


def _red(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaTelefono) -> None:
    """Frena el rumor: los rumores son bolitas que viajan por las conexiones; el escudo las ataja y la onda
    (Espacio) vuelve inmunes a los que toca."""
    p, pos = v.en_vivo, posiciones(v.grafo)
    if p is None:
        resumen = "La red esta en calma: no hay rumores corriendo."
    else:
        resumen = f"Frenados {p.frenados}   |   La creen {p.creen}   |   Inmunes {p.contar(INMUNE)}"
    sup.blit(fuentes.normal.render(resumen, True, tema.texto), (TELEFONO.x + px(22), TELEFONO.y + px(94)))
    for a in v.grafo.aristas():
        pygame.draw.line(sup, tema.borde, pos[a.origen], pos[a.destino], max(1, round(px(3) * a.peso)))
    for c in v.grafo.vertices():
        estado = p.estado[c.id] if p is not None else SIN_ENTERARSE
        activo = p is not None and (c.id in p.rumor or c.id in p.desmentido)
        edad = (v.pulsos or {}).get(c.id)
        if edad is not None and edad < PULSO:   # le acaba de llegar: un anillo que crece y se apaga
            color = tema.bueno if estado == INMUNE else tema.malo
            pygame.draw.circle(sup, (*color, round(220 * (1 - edad / PULSO))), pos[c.id],
                               RADIO + round(px(26) * edad / PULSO), px(3))
        _nodo(sup, tema, pos[c.id], estado, activo, v.t)
    for centro, edad in v.ondas:   # la onda de desmentido crece y se apaga
        r = round(radio_onda() * min(1.0, edad / ONDA))
        pygame.draw.circle(sup, (*tema.bueno, round(200 * (1 - edad / ONDA))), a_pantalla(centro), max(1, r), px(4))
    if p is not None:   # los rumores en camino: bolitas que se mueven por su arista
        for viaje in p.viajes:
            centro = a_pantalla(p.posicion_viaje(viaje))
            pygame.draw.circle(sup, tema.texto, centro, px(7))
            pygame.draw.circle(sup, tema.malo, centro, px(5))
    escudo = a_pantalla(v.escudo)   # el escudo del jugador: anillo con una cruz al centro
    r = radio_escudo(v.extendido)
    color = tema.bueno if v.atajo > 0 else tema.acento   # al atajar, el escudo se ilumina y crece un poco
    r += round(px(6) * v.atajo / 0.35)
    pygame.draw.circle(sup, (*color, 60), escudo, r)
    pygame.draw.circle(sup, color, escudo, r, px(3))
    pygame.draw.line(sup, tema.acento, (escudo[0] - px(6), escudo[1]), (escudo[0] + px(6), escudo[1]), px(2))
    pygame.draw.line(sup, tema.acento, (escudo[0], escudo[1] - px(6)), (escudo[0], escudo[1] + px(6)), px(2))
    _leyenda(sup, fuentes, tema)
    caja = pygame.Rect(TELEFONO.x + px(18), TELEFONO.y + px(404), TELEFONO.w - px(36), px(120))
    pygame.draw.rect(sup, tema.fondo, caja)
    pygame.draw.rect(sup, tema.borde, caja, px(2))
    for k, linea in enumerate(("Mueve el escudo y ataja las bolitas rojas antes de que lleguen.",
                               "Espacio: desmentido en onda (vuelve inmunes a los que toca).")):
        sup.blit(fuentes.chica.render(linea, True, tema.texto), (caja.x + px(14), caja.y + px(10) + k * px(22)))
    falta = p.enfriando["onda"] if p is not None else 0.0
    barra = pygame.Rect(caja.x + px(14), caja.y + px(66), caja.w - px(28), px(14))
    pygame.draw.rect(sup, tema.panel, barra)
    lleno = 1 - falta / ENFRIAMIENTO["onda"] if p is not None else 0
    pygame.draw.rect(sup, tema.bueno, (barra.x, barra.y, round(barra.w * lleno), barra.h))
    estado = ("Sin rumor" if p is None else "Desmentido listo (Espacio)" if falta == 0
              else f"Recargando {math.ceil(falta)} s")
    sup.blit(fuentes.chica.render(estado, True, tema.bueno if p is not None and falta == 0 else tema.texto_off),
             (barra.x, barra.bottom + px(6)))


def radio_escudo(extendido: bool) -> int:
    """En pixeles; con tiempo extendido es mas grande (atajar es mas facil)."""
    return round(AREA_RED.h * RADIO_ESCUDO * (1.4 if extendido else 1.0))


def radio_onda() -> int:
    return round(AREA_RED.h * RADIO_ONDA)


def a_pantalla(p: tuple[float, float]) -> tuple[int, int]:
    return round(AREA_RED.x + p[0] * AREA_RED.w), round(AREA_RED.y + p[1] * AREA_RED.h)


def de_pantalla(punto: tuple[int, int]) -> tuple[float, float]:
    """Del raton a la posicion normalizada de la red (acotada al area)."""
    return (min(1.0, max(0.0, (punto[0] - AREA_RED.x) / AREA_RED.w)),
            min(1.0, max(0.0, (punto[1] - AREA_RED.y) / AREA_RED.h)))


ASPECTO = AREA_RED.w / AREA_RED.h   # para que el radio del escudo sea redondo en pantalla


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
        pygame.draw.rect(sup, tema.bueno, pygame.Rect(x - r, y - r, 2 * r, 2 * r))


def _leyenda(sup: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
    x, y = TELEFONO.x + px(30), TELEFONO.y + px(372)
    for estado, texto in ((SIN_ENTERARSE, "No sabe"), (ENTERADO, "La cree"), (COMPARTIO, "La comparte"),
                          (INMUNE, "Inmune")):
        _nodo(sup, tema, (x, y + px(8)), estado, False, 0)
        img = fuentes.chica.render(texto, True, tema.texto)
        sup.blit(img, (x + RADIO + px(6), y))
        x += RADIO + img.get_width() + px(26)


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
        pygame.draw.rect(sup, tema.fondo, caja)
        pygame.draw.rect(sup, tema.acento if nueva else tema.borde, caja, px(2))
        _icono(sup, tema, n["tipo"], (caja.x + px(26), caja.centery), px(14), 0)
        sup.blit(fuentes.normal.render(n["titulo"], True, tema.texto), (caja.x + px(50), caja.y + px(6)))
        linea = ajustar_texto(n["texto"], fuentes.chica, caja.w - px(62))[0]
        sup.blit(fuentes.chica.render(linea, True, tema.texto), (caja.x + px(50), caja.y + px(34)))
        y += caja.h + px(8)


ETIQUETAS = {"formato": "Formato", "titular": "Titular", "imagen": "Imagen", "fuente": "Fuente", "tono": "Tono"}


def _publicar(sup: pygame.Surface, fuentes: Fuentes, tema: Tema, p: VistaPublicar) -> None:
    for i, (pieza, opcion) in enumerate(p.filas):
        r = rect_fila(i)
        activa = i == p.fila
        pygame.draw.rect(sup, tema.boton if activa else tema.fondo, r)
        pygame.draw.rect(sup, tema.acento if activa else tema.borde, r, px(2))
        color = tema.boton_texto if activa else tema.texto
        sup.blit(fuentes.chica.render(ETIQUETAS[pieza], True, color), (r.x + px(10), r.y + px(10)))
        texto = fuentes.chica.render(f"<  {opcion}  >", True, color)
        sup.blit(texto, texto.get_rect(midright=(r.right - px(10), r.centery)))
    e = p.evaluacion
    y = TELEFONO.y + px(334)
    for nombre, valor, color in (("Veracidad", e.veracidad, tema.malo if e.es_falsa else tema.bueno),
                                 ("Alcance", e.alcance_100, tema.acento),
                                 ("Riesgo de conflicto", e.riesgo, tema.malo)):
        sup.blit(fuentes.chica.render(f"{nombre} {valor}", True, tema.texto), (TELEFONO.x + px(22), y))
        barra = pygame.Rect(TELEFONO.x + px(220), y + px(4), TELEFONO.w - px(242), px(12))
        pygame.draw.rect(sup, tema.fondo, barra)
        pygame.draw.rect(sup, color, (barra.x, barra.y, round(barra.w * valor / 100), barra.h))
        y += px(26)
    color = tema.bueno if e.convivencia > 0 else tema.malo if e.convivencia < 0 else tema.texto
    sup.blit(fuentes.chica.render(f"Convivencia {e.convivencia:+}", True, color), (TELEFONO.x + px(22), y))
    y += px(26)
    if e.es_falsa or e.riesgo >= 50:
        aviso = "Puede volverse viral, pero luego te costara credibilidad."
        sup.blit(fuentes.chica.render(aviso, True, tema.malo), (TELEFONO.x + px(22), y))
    lista = p.enfriamiento == 0 and not p.en_curso
    pygame.draw.rect(sup, tema.boton if lista else tema.boton_off, RECT_PUBLICAR)
    if p.enfriamiento > 0:
        lleno = RECT_PUBLICAR.w * (1 - p.enfriamiento / p.enfriamiento_total)
        pygame.draw.rect(sup, tema.boton, (RECT_PUBLICAR.x, RECT_PUBLICAR.y, round(lleno), RECT_PUBLICAR.h))
    pygame.draw.rect(sup, tema.acento if lista else tema.texto_off, RECT_PUBLICAR, px(2))
    texto = ("Publicar (Enter)" if lista else "Tu post sigue circulando" if p.en_curso
             else f"Podras publicar en {math.ceil(p.enfriamiento)} s")
    img = fuentes.normal.render(texto, True, tema.boton_texto if lista else tema.texto_off)
    sup.blit(img, img.get_rect(center=RECT_PUBLICAR.center))


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
    pygame.draw.rect(pantalla, tema.panel, rect)
    pygame.draw.rect(pantalla, tema.malo if late else tema.borde, rect, px(4 if late else 2))
    cuerpo = pygame.Rect(0, 0, px(18), px(28))
    cuerpo.center = (rect.x + px(22), rect.centery)
    pygame.draw.rect(pantalla, tema.texto, cuerpo, px(2))
    pygame.draw.circle(pantalla, tema.texto, (cuerpo.centerx, cuerpo.bottom - px(5)), px(2))
    img = fuentes.chica.render("T: telefono", True, tema.texto)
    pantalla.blit(img, img.get_rect(midleft=(cuerpo.right + px(8), rect.centery)))
    if sin_leer:
        globo = (rect.right - px(4), rect.y + px(4))
        pygame.draw.circle(pantalla, tema.malo, globo, px(11))
        n = fuentes.chica.render(str(min(sin_leer, 9)), True, tema.fondo)
        pantalla.blit(n, n.get_rect(center=globo))
