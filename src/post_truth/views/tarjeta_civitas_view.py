"""Vista: tarjeta tipo post de Civitas, con zonas clicables que esconden pistas.

Solo dibuja lo que le entrega el controlador (la noticia, el estado de la `Investigacion` y la zona
bajo el mouse) y responde "que zona hay bajo este punto"; no cambia el modelo. Todo se dibuja con
formas de Pygame (avatar, imagen placeholder, corazon y globo de comentarios) y con colores del tema.

Cada zona con pista muestra una insignia con su tecla (A S D F G) y puntos de costo; al revisarla
la insignia pasa a una forma segun lo hallado: triangulo (alerta), circulo con visto (confianza) o
circulo con guion (neutra), asi que no depende solo del color (daltonismo).

Ojo: el titulo del evento NO se muestra en la tarjeta. Titulos como "Rumor sobre el colegio" delatarian
que la noticia es falsa antes de investigar.
"""
from dataclasses import dataclass

import pygame

from post_truth.config import px
from post_truth.models import NewsEvent
from post_truth.models.pistas import Investigacion, Pista, Senal, ZonaTarjeta
from post_truth.models.publicacion import Avatar
from post_truth.views.componentes import Fuentes, ajustar_texto, dibujar_texto_ajustado
from post_truth.views.iconos import rayo
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import Tema
from post_truth.views.zona_view import dibujar_fondo_zona

TECLAS_PISTA = "ASDFG"   # tecla de la 1.a, 2.a... pista de la noticia (como Q W E R para moverse)
MAX_LINEAS_TEXTO = 3
RESERVA_INSIGNIA = px(70)    # px a la derecha de fuente y texto que se dejan libres para la insignia y el costo


@dataclass
class EstadoTarjeta:
    """Lo que la vista necesita para dibujar la tarjeta de la publicacion actual."""
    evento: NewsEvent
    investigacion: Investigacion
    hover: ZonaTarjeta | None = None   # zona con pista bajo el mouse


def _layout(rect: pygame.Rect) -> dict[ZonaTarjeta, pygame.Rect]:
    """Rectangulo de cada parte de la tarjeta (relativo a `rect`). Es la unica fuente de verdad: lo
    usan el dibujo y la deteccion de clics."""
    m = px(10)
    x, y, w = rect.x + m, rect.y + m, rect.width - 2 * m
    return {
        ZonaTarjeta.AUTOR: pygame.Rect(x, y, w - px(112), px(50)),            # avatar + nombre
        ZonaTarjeta.FECHA: pygame.Rect(rect.right - px(112), y, px(102), px(50)),  # fecha (arriba a la derecha)
        ZonaTarjeta.FUENTE: pygame.Rect(x, y + px(54), w, px(24)),
        ZonaTarjeta.TEXTO: pygame.Rect(x, y + px(80), w, px(68)),
        ZonaTarjeta.IMAGEN: pygame.Rect(x, y + px(152), w, (rect.bottom - m - px(28) - px(4)) - (y + px(152))),   # hasta un poco antes de las reacciones
        ZonaTarjeta.ESTADISTICAS: pygame.Rect(x, rect.bottom - m - px(28), w, px(28)),
    }


def zona_en(rect: pygame.Rect, punto: tuple[int, int], evento: NewsEvent) -> ZonaTarjeta | None:
    """Zona clicable (con pista) bajo `punto`, o None. Las zonas sin pista no responden."""
    con_pista = {p.zona for p in evento.clues}
    for zona, r in _layout(rect).items():
        if zona in con_pista and r.collidepoint(punto):
            return zona
    return None


def _recortar(fuente: pygame.font.Font, texto: str, ancho: int) -> str:
    """Corta con puntos suspensivos para que el texto no pase de `ancho` px."""
    if fuente.size(texto)[0] <= ancho:
        return texto
    while texto and fuente.size(texto + "...")[0] > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "..."


def _centro_insignia(zona: ZonaTarjeta, r: pygame.Rect) -> tuple[int, int]:
    """Esquina libre de cada zona: abajo a la derecha en autor y fecha (el nombre y la hora quedan
    arriba), arriba a la derecha en las demas (donde el texto reserva margen)."""
    if zona in (ZonaTarjeta.AUTOR, ZonaTarjeta.FECHA):
        return r.right - px(14), r.bottom - px(12)
    return r.right - px(14), r.y + px(12)


def pista_con_tecla(evento: NewsEvent, letra: str) -> Pista | None:
    """Pista asociada a una tecla (A S D F G, segun el orden en que vienen en la noticia)."""
    i = TECLAS_PISTA.find(letra.upper())
    return evento.clues[i] if 0 <= i < len(evento.clues) else None


# --- piezas ---------------------------------------------------------------------------------------
def _avatar(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, avatar: Avatar, nombre: str,
            rect: pygame.Rect) -> None:
    if avatar.tipo == "retrato" and avatar.aspecto is not None:
        dibujar_retrato(pantalla, avatar.aspecto, tema, rect)
    elif avatar.tipo == "anonimo":    # silueta gris: cuenta sin foto ni identidad
        pygame.draw.circle(pantalla, tema.borde, rect.center, rect.width // 2)
        pygame.draw.circle(pantalla, tema.panel, (rect.centerx, rect.centery - px(5)), rect.width // 5)
        pygame.draw.ellipse(pantalla, tema.panel, (rect.x + px(9), rect.centery + px(3), rect.width - px(18), rect.height // 2))
    else:                              # institucional: escudo con la inicial
        color = tema.rol[avatar.color]
        pygame.draw.rect(pantalla, color, rect, border_radius=px(10))
        pygame.draw.rect(pantalla, tema.borde, rect, width=px(2), border_radius=px(10))
        inicial = fuentes.grande.render(nombre.strip("@")[0].upper(), True, tema.fondo)
        pantalla.blit(inicial, inicial.get_rect(center=rect.center))


def _corazon(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int]) -> None:
    x, y = centro
    pygame.draw.circle(pantalla, color, (x - px(4), y - px(2)), px(5))
    pygame.draw.circle(pantalla, color, (x + px(4), y - px(2)), px(5))
    pygame.draw.polygon(pantalla, color, [(x - px(9), y), (x + px(9), y), (x, y + px(10))])


def _globo(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int]) -> None:
    x, y = centro
    pygame.draw.rect(pantalla, color, (x - px(9), y - px(7), px(18), px(12)), border_radius=px(4))
    pygame.draw.polygon(pantalla, color, [(x - px(4), y + px(4)), (x + px(1), y + px(4)), (x - px(5), y + px(10))])


def _insignia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, centro: tuple[int, int], pista: Pista,
              descubierta: bool, letra: str) -> None:
    x, y = centro
    if not descubierta:   # "aqui hay algo que revisar": tecla + costo en puntos de energia
        pygame.draw.circle(pantalla, tema.acento, centro, px(11))
        glifo = fuentes.chica.render(letra, True, tema.fondo)
        pantalla.blit(glifo, glifo.get_rect(center=centro))
        for i in range(pista.costo):   # lo que cuesta revisarla: un rayo de energia por unidad
            rayo(pantalla, tema.acento, (x - px(24) - i * px(14), y), px(7))
    elif pista.senal is Senal.FALSA:
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - px(12)), (x + px(13), y + px(10)), (x - px(13), y + px(10))])
        signo = fuentes.chica.render("!", True, tema.fondo)
        pantalla.blit(signo, signo.get_rect(center=(x, y + px(2))))
    elif pista.senal is Senal.VERDADERA:
        pygame.draw.circle(pantalla, tema.bueno, centro, px(12))
        pygame.draw.lines(pantalla, tema.fondo, False, [(x - px(6), y), (x - px(2), y + px(5)), (x + px(6), y - px(5))], px(3))
    else:
        pygame.draw.circle(pantalla, tema.borde, centro, px(12))
        pygame.draw.line(pantalla, tema.texto, (x - px(5), y), (x + px(5), y), px(3))


def _tooltip(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, tarjeta: pygame.Rect, zona: pygame.Rect,
             pista: Pista, descubierta: bool) -> None:
    """Cuadro junto a la zona: el hallazgo si ya se reviso; si no, solo el costo (sin delatar nada)."""
    ancho = px(290)
    texto = (f"{pista.titulo}\n{pista.hallazgo}" if descubierta
             else f"Clic para investigar\nCosto: {pista.costo} de energia")
    lineas = ajustar_texto(texto, fuentes.chica, ancho - px(20))
    alto = len(lineas) * (fuentes.chica.get_linesize() + px(2)) + px(16)
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.midtop = (zona.centerx, zona.bottom + px(6))
    if caja.bottom > tarjeta.bottom:                 # no cabe abajo: va arriba de la zona
        caja.midbottom = (zona.centerx, zona.top - px(6))
    caja.clamp_ip(tarjeta)
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(8))
    pygame.draw.rect(pantalla, tema.acento, caja, width=px(2), border_radius=px(8))
    y = caja.y + px(8)
    for i, linea in enumerate(lineas):
        color = tema.acento if i == 0 and descubierta else tema.texto
        pantalla.blit(fuentes.chica.render(linea, True, color), (caja.x + px(10), y))
        y += fuentes.chica.get_linesize() + px(2)


# --- tarjeta completa -------------------------------------------------------------------------------
def dibujar_tarjeta(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect, evento: NewsEvent,
                    investigacion: Investigacion, hover: ZonaTarjeta | None = None) -> None:
    zonas = _layout(rect)
    pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, rect, width=px(2), border_radius=px(12))

    autor = evento.author
    if autor is not None:
        r = zonas[ZonaTarjeta.AUTOR]
        _avatar(pantalla, fuentes, tema, autor.avatar, autor.nombre, pygame.Rect(r.x, r.y, px(48), px(48)))
        nombre = _recortar(fuentes.normal, autor.nombre, r.width - px(58) - px(4))
        pantalla.blit(fuentes.normal.render(nombre, True, tema.texto), (r.x + px(58), r.y + px(2)))
        pantalla.blit(fuentes.chica.render("en Civitas", True, tema.borde), (r.x + px(58), r.y + px(28)))
    fecha = fuentes.chica.render(evento.date, True, tema.texto)
    pantalla.blit(fecha, fecha.get_rect(topright=(zonas[ZonaTarjeta.FECHA].right - px(4), zonas[ZonaTarjeta.FECHA].y + px(4))))
    fuente_r = zonas[ZonaTarjeta.FUENTE]
    texto_fuente = _recortar(fuentes.chica, f"Fuente: {evento.source}", fuente_r.width - RESERVA_INSIGNIA)
    pantalla.blit(fuentes.chica.render(texto_fuente, True, tema.borde), (fuente_r.x + px(2), fuente_r.y + px(3)))

    # Texto de la publicacion (maximo 3 lineas; si sobra, se corta con puntos suspensivos)
    r = zonas[ZonaTarjeta.TEXTO]
    lineas = ajustar_texto(evento.content, fuentes.chica, r.width - RESERVA_INSIGNIA)
    if len(lineas) > MAX_LINEAS_TEXTO:
        lineas = lineas[:MAX_LINEAS_TEXTO]
        lineas[-1] = lineas[-1].rstrip(" .,") + "..."
    for i, linea in enumerate(lineas):
        pantalla.blit(fuentes.chica.render(linea, True, tema.texto), (r.x + px(2), r.y + px(2) + i * (fuentes.chica.get_linesize() + px(1))))

    # Imagen placeholder: el fondo de una zona de la ciudad, con marco, marca de foto y pie
    r = zonas[ZonaTarjeta.IMAGEN]
    if evento.image is not None:
        foto = pygame.Surface(r.size)
        dibujar_fondo_zona(foto, evento.image.motivo, tema, foto.get_rect())
        pantalla.blit(foto, r)
        pygame.draw.rect(pantalla, tema.borde, r, width=px(2))
        if evento.image.pie:
            banda = pygame.Rect(r.x, r.bottom - px(26), r.width, px(26))
            velo = pygame.Surface(banda.size, pygame.SRCALPHA)
            velo.fill((*tema.fondo, 200))
            pantalla.blit(velo, banda)
            pantalla.blit(fuentes.chica.render(evento.image.pie, True, tema.texto), (banda.x + px(6), banda.y + px(3)))
        etiqueta = fuentes.chica.render("FOTO", True, tema.fondo)
        marca = etiqueta.get_rect(topleft=(r.x + px(6), r.y + px(6))).inflate(px(10), px(4))
        pygame.draw.rect(pantalla, tema.detalle, marca, border_radius=px(6))
        pantalla.blit(etiqueta, etiqueta.get_rect(center=marca.center))

    # Reacciones: corazon + likes, globo + comentarios
    r = zonas[ZonaTarjeta.ESTADISTICAS]
    _corazon(pantalla, tema.malo, (r.x + px(14), r.centery - px(1)))
    pantalla.blit(fuentes.normal.render(str(evento.likes), True, tema.texto), (r.x + px(30), r.y + px(1)))
    _globo(pantalla, tema.acento, (r.x + px(128), r.centery))
    pantalla.blit(fuentes.normal.render(str(evento.comments), True, tema.texto), (r.x + px(146), r.y + px(1)))

    # Zonas con pista: borde al pasar el mouse e insignia con tecla/costo o con lo hallado
    for i, pista in enumerate(evento.clues):
        zr = zonas[pista.zona]
        descubierta = investigacion.esta_descubierta(pista.id)
        if hover is pista.zona:
            pygame.draw.rect(pantalla, tema.acento, zr.inflate(px(4), px(4)), width=px(2), border_radius=px(8))
        elif descubierta:
            pygame.draw.rect(pantalla, tema.borde, zr.inflate(px(2), px(2)), width=1, border_radius=px(8))
        _insignia(pantalla, fuentes, tema, _centro_insignia(pista.zona, zr), pista, descubierta, TECLAS_PISTA[i])
    if hover is not None:
        pista = next((p for p in evento.clues if p.zona is hover), None)
        if pista is not None:
            _tooltip(pantalla, fuentes, tema, rect, zonas[hover], pista, investigacion.esta_descubierta(pista.id))
