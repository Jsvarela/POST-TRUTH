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

from post_truth.models import NewsEvent
from post_truth.models.pistas import Investigacion, Pista, Senal, ZonaTarjeta
from post_truth.models.publicacion import Avatar
from post_truth.views.componentes import Fuentes, ajustar_texto, dibujar_texto_ajustado
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import Tema
from post_truth.views.zona_view import dibujar_fondo_zona

TECLAS_PISTA = "ASDFG"   # tecla de la 1.a, 2.a... pista de la noticia (como Q W E R para moverse)
MAX_LINEAS_TEXTO = 3
RESERVA_INSIGNIA = 70    # px a la derecha de fuente y texto que se dejan libres para la insignia y el costo


@dataclass
class EstadoTarjeta:
    """Lo que la vista necesita para dibujar la tarjeta de la publicacion actual."""
    evento: NewsEvent
    investigacion: Investigacion
    hover: ZonaTarjeta | None = None   # zona con pista bajo el mouse


def _layout(rect: pygame.Rect) -> dict[ZonaTarjeta, pygame.Rect]:
    """Rectangulo de cada parte de la tarjeta (relativo a `rect`). Es la unica fuente de verdad: lo
    usan el dibujo y la deteccion de clics."""
    x, y, w = rect.x + 10, rect.y + 10, rect.width - 20
    return {
        ZonaTarjeta.AUTOR: pygame.Rect(x, y, w - 112, 50),            # avatar + nombre
        ZonaTarjeta.FECHA: pygame.Rect(rect.right - 112, y, 102, 50),  # fecha (arriba a la derecha)
        ZonaTarjeta.FUENTE: pygame.Rect(x, y + 54, w, 24),
        ZonaTarjeta.TEXTO: pygame.Rect(x, y + 80, w, 68),
        ZonaTarjeta.IMAGEN: pygame.Rect(x, y + 152, w, (rect.bottom - 10 - 28 - 4) - (y + 152)),   # hasta 4 px antes de las reacciones
        ZonaTarjeta.ESTADISTICAS: pygame.Rect(x, rect.bottom - 10 - 28, w, 28),
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
        return r.right - 14, r.bottom - 12
    return r.right - 14, r.y + 12


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
        pygame.draw.circle(pantalla, tema.panel, (rect.centerx, rect.centery - 5), rect.width // 5)
        pygame.draw.ellipse(pantalla, tema.panel, (rect.x + 9, rect.centery + 3, rect.width - 18, rect.height // 2))
    else:                              # institucional: escudo con la inicial
        color = tema.rol[avatar.color]
        pygame.draw.rect(pantalla, color, rect, border_radius=10)
        pygame.draw.rect(pantalla, tema.borde, rect, width=2, border_radius=10)
        inicial = fuentes.grande.render(nombre.strip("@")[0].upper(), True, tema.fondo)
        pantalla.blit(inicial, inicial.get_rect(center=rect.center))


def _corazon(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int]) -> None:
    x, y = centro
    pygame.draw.circle(pantalla, color, (x - 4, y - 2), 5)
    pygame.draw.circle(pantalla, color, (x + 4, y - 2), 5)
    pygame.draw.polygon(pantalla, color, [(x - 9, y), (x + 9, y), (x, y + 10)])


def _globo(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int]) -> None:
    x, y = centro
    pygame.draw.rect(pantalla, color, (x - 9, y - 7, 18, 12), border_radius=4)
    pygame.draw.polygon(pantalla, color, [(x - 4, y + 4), (x + 1, y + 4), (x - 5, y + 10)])


def _insignia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, centro: tuple[int, int], pista: Pista,
              descubierta: bool, letra: str) -> None:
    x, y = centro
    if not descubierta:   # "aqui hay algo que revisar": tecla + costo en puntos de energia
        pygame.draw.circle(pantalla, tema.acento, centro, 10)
        glifo = fuentes.chica.render(letra, True, tema.fondo)
        pantalla.blit(glifo, glifo.get_rect(center=centro))
        for i in range(pista.costo):
            pygame.draw.circle(pantalla, tema.acento, (x - 18 - i * 8, y), 3)
    elif pista.senal is Senal.FALSA:
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - 12), (x + 13, y + 10), (x - 13, y + 10)])
        signo = fuentes.chica.render("!", True, tema.fondo)
        pantalla.blit(signo, signo.get_rect(center=(x, y + 2)))
    elif pista.senal is Senal.VERDADERA:
        pygame.draw.circle(pantalla, tema.bueno, centro, 11)
        pygame.draw.lines(pantalla, tema.fondo, False, [(x - 6, y), (x - 2, y + 5), (x + 6, y - 5)], 3)
    else:
        pygame.draw.circle(pantalla, tema.borde, centro, 11)
        pygame.draw.line(pantalla, tema.texto, (x - 5, y), (x + 5, y), 3)


def _tooltip(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, tarjeta: pygame.Rect, zona: pygame.Rect,
             pista: Pista, descubierta: bool) -> None:
    """Cuadro junto a la zona: el hallazgo si ya se reviso; si no, solo el costo (sin delatar nada)."""
    ancho = 270
    texto = (f"{pista.titulo}\n{pista.hallazgo}" if descubierta
             else f"Clic para investigar\nCosto: {pista.costo} de energia")
    lineas = ajustar_texto(texto, fuentes.chica, ancho - 20)
    alto = len(lineas) * (fuentes.chica.get_linesize() + 2) + 16
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.midtop = (zona.centerx, zona.bottom + 6)
    if caja.bottom > tarjeta.bottom:                 # no cabe abajo: va arriba de la zona
        caja.midbottom = (zona.centerx, zona.top - 6)
    caja.clamp_ip(tarjeta)
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=8)
    pygame.draw.rect(pantalla, tema.acento, caja, width=2, border_radius=8)
    y = caja.y + 8
    for i, linea in enumerate(lineas):
        color = tema.acento if i == 0 and descubierta else tema.texto
        pantalla.blit(fuentes.chica.render(linea, True, color), (caja.x + 10, y))
        y += fuentes.chica.get_linesize() + 2


# --- tarjeta completa -------------------------------------------------------------------------------
def dibujar_tarjeta(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect, evento: NewsEvent,
                    investigacion: Investigacion, hover: ZonaTarjeta | None = None) -> None:
    zonas = _layout(rect)
    pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=12)
    pygame.draw.rect(pantalla, tema.borde, rect, width=2, border_radius=12)

    autor = evento.author
    if autor is not None:
        r = zonas[ZonaTarjeta.AUTOR]
        _avatar(pantalla, fuentes, tema, autor.avatar, autor.nombre, pygame.Rect(r.x, r.y, 48, 48))
        nombre = _recortar(fuentes.normal, autor.nombre, r.width - 58 - 4)
        pantalla.blit(fuentes.normal.render(nombre, True, tema.texto), (r.x + 58, r.y + 3))
        pantalla.blit(fuentes.chica.render("en Civitas", True, tema.borde), (r.x + 58, r.y + 28))
    fecha = fuentes.chica.render(evento.date, True, tema.texto)
    pantalla.blit(fecha, fecha.get_rect(topright=(zonas[ZonaTarjeta.FECHA].right - 4, zonas[ZonaTarjeta.FECHA].y + 4)))
    fuente_r = zonas[ZonaTarjeta.FUENTE]
    texto_fuente = _recortar(fuentes.chica, f"Fuente: {evento.source}", fuente_r.width - RESERVA_INSIGNIA)
    pantalla.blit(fuentes.chica.render(texto_fuente, True, tema.borde), (fuente_r.x + 2, fuente_r.y + 3))

    # Texto de la publicacion (maximo 3 lineas; si sobra, se corta con puntos suspensivos)
    r = zonas[ZonaTarjeta.TEXTO]
    lineas = ajustar_texto(evento.content, fuentes.chica, r.width - RESERVA_INSIGNIA)
    if len(lineas) > MAX_LINEAS_TEXTO:
        lineas = lineas[:MAX_LINEAS_TEXTO]
        lineas[-1] = lineas[-1].rstrip(" .,") + "..."
    for i, linea in enumerate(lineas):
        pantalla.blit(fuentes.chica.render(linea, True, tema.texto), (r.x + 2, r.y + 2 + i * (fuentes.chica.get_linesize() + 1)))

    # Imagen placeholder: el fondo de una zona de la ciudad, con marco, marca de foto y pie
    r = zonas[ZonaTarjeta.IMAGEN]
    if evento.image is not None:
        foto = pygame.Surface(r.size)
        dibujar_fondo_zona(foto, evento.image.motivo, tema, foto.get_rect())
        pantalla.blit(foto, r)
        pygame.draw.rect(pantalla, tema.borde, r, width=2)
        if evento.image.pie:
            banda = pygame.Rect(r.x, r.bottom - 22, r.width, 22)
            velo = pygame.Surface(banda.size, pygame.SRCALPHA)
            velo.fill((*tema.fondo, 200))
            pantalla.blit(velo, banda)
            pantalla.blit(fuentes.chica.render(evento.image.pie, True, tema.texto), (banda.x + 6, banda.y + 2))
        etiqueta = fuentes.chica.render("FOTO", True, tema.fondo)
        marca = etiqueta.get_rect(topleft=(r.x + 6, r.y + 6)).inflate(10, 4)
        pygame.draw.rect(pantalla, tema.detalle, marca, border_radius=6)
        pantalla.blit(etiqueta, etiqueta.get_rect(center=marca.center))

    # Reacciones: corazon + likes, globo + comentarios
    r = zonas[ZonaTarjeta.ESTADISTICAS]
    _corazon(pantalla, tema.malo, (r.x + 14, r.centery - 1))
    pantalla.blit(fuentes.normal.render(str(evento.likes), True, tema.texto), (r.x + 30, r.y + 2))
    _globo(pantalla, tema.acento, (r.x + 118, r.centery))
    pantalla.blit(fuentes.normal.render(str(evento.comments), True, tema.texto), (r.x + 134, r.y + 2))

    # Zonas con pista: borde al pasar el mouse e insignia con tecla/costo o con lo hallado
    for i, pista in enumerate(evento.clues):
        zr = zonas[pista.zona]
        descubierta = investigacion.esta_descubierta(pista.id)
        if hover is pista.zona:
            pygame.draw.rect(pantalla, tema.acento, zr.inflate(4, 4), width=2, border_radius=8)
        elif descubierta:
            pygame.draw.rect(pantalla, tema.borde, zr.inflate(2, 2), width=1, border_radius=8)
        _insignia(pantalla, fuentes, tema, _centro_insignia(pista.zona, zr), pista, descubierta, TECLAS_PISTA[i])
    if hover is not None:
        pista = next((p for p in evento.clues if p.zona is hover), None)
        if pista is not None:
            _tooltip(pantalla, fuentes, tema, rect, zonas[hover], pista, investigacion.esta_descubierta(pista.id))
