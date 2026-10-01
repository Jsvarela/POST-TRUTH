"""Vista de la introduccion: laminas dibujadas con formas de Pygame, con fundido y subtitulo.

Solo dibuja los datos que le entrega el controlador (modelo `Intro`, instante `t` de la lamina,
opacidad `alfa`); no avanza nada por su cuenta. Cada lamina se pinta en un lienzo aparte al que se
le aplica la opacidad (fundido). El subtitulo (la caja de dialogo con el texto que se escribe letra
por letra) se dibuja DESPUES, encima y siempre opaco: el texto nunca desaparece con el fundido.

Todos los colores salen del tema activo. Los rumores y las verdades de Civitas se distinguen por
forma (triangulo de advertencia / circulo con visto) ademas de por color, y los candidatos por
peinado y accesorio, para no depender solo del tono (daltonismo).
"""
import math
import random
from typing import Callable

import pygame

from post_truth.models import Role
from post_truth.models.intro import Candidato, Intro, Lamina
from post_truth.models.personaje import Genero, Personaje, ROL_DESCRIPCION
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import CajaDialogo, Fuentes, dibujar_texto_ajustado
from post_truth.views.mapa_view import EstadoMapa, dibujar_mapa
from post_truth.views.personaje_view import dibujar_personaje
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import Tema
from post_truth.views.zona_view import dibujar_fondo_zona

ANCHO, ALTO_ARTE = 1024, 486          # el dibujo ocupa lo de arriba; abajo van el subtitulo y la ayuda
TAMANO_LIENZO = (ANCHO, ALTO_ARTE)
SEGUNDOS_POR_ZONA = 3.2               # cuanto se queda resaltada cada zona en la lamina del mapa
Y_SUELO = 400                         # donde terminan los edificios del horizonte
_ROLES = list(Role)

Pintor = Callable[[pygame.Surface, Fuentes, Tema, Intro, GrafoCiudad, Lamina, float], None]


def _aparicion(t: float, inicio: float, duracion: float = 0.5) -> float:
    """0 antes de `inicio`, sube linealmente hasta 1 en `duracion` segundos y se queda en 1."""
    return max(0.0, min(1.0, (t - inicio) / duracion))


def _texto_con_borde(lienzo: pygame.Surface, fuente: pygame.font.Font, texto: str, color: tuple[int, int, int],
                     borde: tuple[int, int, int], centro: tuple[int, int], alfa: float = 1.0) -> None:
    """Texto legible sobre cualquier fondo: se dibuja primero en el color de borde, desplazado."""
    img = fuente.render(texto, True, color)
    sombra = fuente.render(texto, True, borde)
    for superficie in (img, sombra):
        superficie.set_alpha(round(255 * alfa))
    rect = img.get_rect(center=centro)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        lienzo.blit(sombra, rect.move(dx, dy))
    lienzo.blit(img, rect)


# --- horizonte de la ciudad (laminas "ciudad" y "cierre") ---------------------------------------
_rng = random.Random(3)  # fijo: la ciudad dibujada es siempre la misma
_EDIFICIOS: list[tuple[int, int, int]] = []
_x = -10
while _x < ANCHO:
    _w = _rng.randint(56, 98)
    _EDIFICIOS.append((_x, _w, _rng.randint(90, 190)))
    _x += _w + _rng.randint(2, 10)
# (indice de edificio, x, y, orden): `orden` define cuando se enciende cada ventana
_VENTANAS: list[tuple[int, int, int, int]] = []
for _i, (_bx, _bw, _bh) in enumerate(_EDIFICIOS):
    for _fila in range(_bh // 28):
        for _col in range(max(1, _bw // 22)):
            _VENTANAS.append((_i, _bx + 9 + _col * 20, Y_SUELO - _bh + 12 + _fila * 28, _rng.randint(0, 100)))
_ESTRELLAS = [(_rng.randint(10, ANCHO - 10), _rng.randint(8, 190), _rng.random() * 6) for _ in range(46)]


def _horizonte(lienzo: pygame.Surface, tema: Tema, t: float, ventanas_encendidas: bool = True) -> None:
    lienzo.fill(tema.cielo)
    for x, y, fase in _ESTRELLAS:
        brillo = 0.5 + 0.5 * math.sin(t * 1.6 + fase)
        pygame.draw.circle(lienzo, tema.texto, (x, y), 2 if brillo > 0.6 else 1)
    pygame.draw.circle(lienzo, tema.detalle, (880, 86), 30)                    # luna
    pygame.draw.circle(lienzo, tema.cielo, (894, 78), 26)
    for x, w, h in _EDIFICIOS:
        pygame.draw.rect(lienzo, tema.edificio, (x, Y_SUELO - h, w, h))
        pygame.draw.rect(lienzo, tema.borde, (x, Y_SUELO - h, w, h), 2)
    if ventanas_encendidas:  # las ventanas se encienden una a una con el tiempo
        for _, x, y, orden in _VENTANAS:
            if t * 24 > orden:
                pygame.draw.rect(lienzo, tema.detalle, (x, y, 9, 13), border_radius=2)
    pygame.draw.rect(lienzo, tema.suelo, (0, Y_SUELO, ANCHO, ALTO_ARTE - Y_SUELO))


# --- lamina 1: Ciudad Nova y las elecciones ------------------------------------------------------
def _lamina_ciudad(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, intro: Intro, ciudad: GrafoCiudad,
                   lamina: Lamina, t: float) -> None:
    _horizonte(lienzo, tema, t)
    titulo = pygame.transform.smoothscale(fuentes.titulo.render(lamina.titulo.upper(), True, tema.texto), (620, 88))
    sombra = pygame.transform.smoothscale(fuentes.titulo.render(lamina.titulo.upper(), True, tema.fondo), (620, 88))
    a = _aparicion(t, 0.7, 1.0)
    for superficie in (titulo, sombra):
        superficie.set_alpha(round(255 * a))
    centro = (ANCHO // 2, 96 - round(12 * (1 - a)))   # el titulo sube suavemente al aparecer
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        lienzo.blit(sombra, sombra.get_rect(center=(centro[0] + dx, centro[1] + dy)))
    lienzo.blit(titulo, titulo.get_rect(center=centro))
    _texto_con_borde(lienzo, fuentes.grande, "Elecciones para alcalde", tema.acento, tema.fondo,
                     (ANCHO // 2, 160), _aparicion(t, 1.6, 0.8))


# --- lamina 2: la ciudad y sus zonas -------------------------------------------------------------
def _lamina_zonas(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, intro: Intro, ciudad: GrafoCiudad,
                  lamina: Lamina, t: float) -> None:
    lienzo.fill(tema.fondo)
    idx = int(t / SEGUNDOS_POR_ZONA) % len(intro.zonas)
    zona = intro.zonas[idx]
    mapa = pygame.Rect(36, 30, 520, 420)
    dibujar_mapa(lienzo, fuentes, tema, mapa, EstadoMapa(ciudad, actual=zona.id))
    # Tarjeta de la zona resaltada: su fondo (el mismo de la escena) y su descripcion
    tarjeta = pygame.Rect(590, 30, 400, 420)
    pygame.draw.rect(lienzo, tema.panel, tarjeta, border_radius=14)
    foto = pygame.Rect(tarjeta.x + 12, tarjeta.y + 12, tarjeta.width - 24, 190)
    sub = pygame.Surface(foto.size)
    dibujar_fondo_zona(sub, zona.id, tema, sub.get_rect())
    lienzo.blit(sub, foto)
    pygame.draw.rect(lienzo, tema.borde, foto, width=2)
    pygame.draw.rect(lienzo, tema.borde, tarjeta, width=2, border_radius=14)
    nombre = ciudad.zona(zona.id).nombre
    lienzo.blit(fuentes.grande.render(nombre, True, tema.acento), (tarjeta.x + 18, foto.bottom + 14))
    dibujar_texto_ajustado(lienzo, fuentes.normal, zona.descripcion, tema.texto,
                           pygame.Rect(tarjeta.x + 18, foto.bottom + 56, tarjeta.width - 36, 150))


# --- lamina 3: Civitas y los primeros rumores ----------------------------------------------------
def _icono_rumor(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, centro: tuple[int, int]) -> None:
    x, y = centro   # triangulo de advertencia con "!"
    pygame.draw.polygon(lienzo, tema.malo, [(x, y - 12), (x + 13, y + 10), (x - 13, y + 10)])
    signo = fuentes.chica.render("!", True, tema.fondo)
    lienzo.blit(signo, signo.get_rect(center=(x, y + 2)))


def _icono_verdad(lienzo: pygame.Surface, tema: Tema, centro: tuple[int, int]) -> None:
    x, y = centro   # circulo con visto
    pygame.draw.circle(lienzo, tema.bueno, (x, y), 12)
    pygame.draw.lines(lienzo, tema.fondo, False, [(x - 6, y), (x - 2, y + 5), (x + 7, y - 5)], 3)


def _lamina_civitas(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, intro: Intro, ciudad: GrafoCiudad,
                    lamina: Lamina, t: float) -> None:
    lienzo.fill(tema.fondo)
    for i in range(7):  # burbujas "?" que suben por los costados: el rumor flota en el aire
        x = 70 + (i % 2) * 150 + (i // 2) * 12 if i < 4 else 790 + (i % 2) * 120 + (i - 4) * 10
        y = ALTO_ARTE - ((t * 30 + i * 90) % (ALTO_ARTE + 40))
        pygame.draw.circle(lienzo, tema.borde, (round(x), round(y)), 17, 2)
        signo = fuentes.chica.render("?", True, tema.borde)
        lienzo.blit(signo, signo.get_rect(center=(round(x), round(y))))
    telefono = pygame.Rect(312, 6, 400, 456)
    pygame.draw.rect(lienzo, tema.panel, telefono, border_radius=22)
    pygame.draw.rect(lienzo, tema.borde, telefono, width=3, border_radius=22)
    lienzo.blit(fuentes.grande.render("Civitas", True, tema.acento), (telefono.x + 20, telefono.y + 12))
    for i, post in enumerate(intro.publicaciones):
        a = _aparicion(t, 0.9 + i * 1.1, 0.5)
        if a <= 0:
            continue
        tarjeta = pygame.Rect(telefono.x + 14, telefono.y + 58 + i * 98 + round(16 * (1 - a)), telefono.width - 28, 92)
        capa = pygame.Surface(tarjeta.size, pygame.SRCALPHA)
        interior = capa.get_rect()
        es_rumor = post.tipo == "rumor"
        color = tema.malo if es_rumor else tema.bueno
        pygame.draw.rect(capa, (*tema.fondo, 255), interior, border_radius=10)
        grosor = 3 if es_rumor and int(t * 3) % 2 == 0 else 2   # el rumor late
        pygame.draw.rect(capa, (*color, 255), interior, width=grosor, border_radius=10)
        pygame.draw.circle(capa, tema.rol[i % 4], (30, 28), 18)       # avatar
        inicial = fuentes.normal.render(post.autor.strip("@")[0].upper(), True, tema.fondo)
        capa.blit(inicial, inicial.get_rect(center=(30, 28)))
        capa.blit(fuentes.chica.render(post.autor, True, tema.acento), (58, 8))
        dibujar_texto_ajustado(capa, fuentes.chica, post.texto, tema.texto, pygame.Rect(58, 28, 270, 44), 2)
        capa.blit(fuentes.chica.render(f"{post.reacciones} reacciones", True, tema.texto), (58, 68))
        (_icono_rumor(capa, fuentes, tema, (interior.right - 24, 24)) if es_rumor
         else _icono_verdad(capa, tema, (interior.right - 24, 24)))
        capa.set_alpha(round(255 * a))
        lienzo.blit(capa, tarjeta)
    # Leyenda: forma + color
    _icono_rumor(lienzo, fuentes, tema, (telefono.x - 150, telefono.y + 40))
    lienzo.blit(fuentes.normal.render("Rumor", True, tema.texto), (telefono.x - 130, telefono.y + 29))
    _icono_verdad(lienzo, tema, (telefono.right + 28, telefono.y + 40))
    lienzo.blit(fuentes.normal.render("Verdad", True, tema.texto), (telefono.right + 48, telefono.y + 29))


# --- laminas 4 y 5: los candidatos ---------------------------------------------------------------
def _tarjeta_candidato(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, c: Candidato, rect: pygame.Rect,
                       a: float) -> None:
    capa = pygame.Surface(rect.size, pygame.SRCALPHA)
    interior = capa.get_rect()
    pygame.draw.rect(capa, (*tema.panel, 255), interior, border_radius=16)
    pygame.draw.rect(capa, (*tema.borde, 255), interior, width=2, border_radius=16)
    dibujar_retrato(capa, c.aspecto, tema, pygame.Rect(interior.centerx - 95, 14, 190, 228))
    nombre = fuentes.grande.render(c.nombre, True, tema.texto)
    capa.blit(nombre, nombre.get_rect(midtop=(interior.centerx, 250)))
    lema = fuentes.normal.render(f"\"{c.lema}\"", True, tema.acento)
    capa.blit(lema, lema.get_rect(midtop=(interior.centerx, 288)))
    capa.blit(fuentes.chica.render("Propuesta", True, tema.acento), (22, 326))
    dibujar_texto_ajustado(capa, fuentes.normal, c.propuesta, tema.texto,
                           pygame.Rect(22, 346, interior.width - 44, 80), 2)
    capa.set_alpha(round(255 * a))
    lienzo.blit(capa, rect.move(0, round(18 * (1 - a))))


def _lamina_candidatos(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, intro: Intro, ciudad: GrafoCiudad,
                       lamina: Lamina, t: float) -> None:
    lienzo.fill(tema.fondo)
    n = len(lamina.candidatos)
    ancho, alto, hueco = 420, 440, 44
    x0 = (ANCHO - (n * ancho + (n - 1) * hueco)) // 2
    for i, id in enumerate(lamina.candidatos):
        _tarjeta_candidato(lienzo, fuentes, tema, intro.candidato(id),
                           pygame.Rect(x0 + i * (ancho + hueco), 22, ancho, alto), _aparicion(t, 0.7 + i * 0.9, 0.6))


# --- lamina 6: cierre, los cuatro roles ------------------------------------------------------------
def _lamina_cierre(lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema, intro: Intro, ciudad: GrafoCiudad,
                   lamina: Lamina, t: float) -> None:
    _horizonte(lienzo, tema, t, ventanas_encendidas=False)   # horizonte apagado: el texto de los roles manda
    _texto_con_borde(lienzo, fuentes.titulo, "Elige quien seras", tema.texto, tema.fondo, (ANCHO // 2, 48),
                     _aparicion(t, 0.2, 0.6))
    for i, rol in enumerate(_ROLES):
        a = _aparicion(t, 0.6 + i * 0.5, 0.6)
        if a <= 0:
            continue
        x = 24 + i * 248
        capa = pygame.Surface((236, 380), pygame.SRCALPHA)
        pygame.draw.rect(capa, (*tema.panel, 240), capa.get_rect(), border_radius=16)
        pygame.draw.rect(capa, (*tema.borde, 255), capa.get_rect(), width=2, border_radius=16)
        dibujar_personaje(capa, Personaje(rol, Genero.MUJER if i % 2 else Genero.HOMBRE, 0), tema,
                          pygame.Rect(28, 8, 180, 236), animo=1 if a >= 1 else 0)
        nombre = fuentes.normal.render(rol.value, True, tema.acento)
        capa.blit(nombre, nombre.get_rect(midtop=(118, 252)))
        dibujar_texto_ajustado(capa, fuentes.chica, ROL_DESCRIPCION[rol], tema.texto, pygame.Rect(14, 282, 208, 90), 2)
        capa.set_alpha(round(255 * a))
        lienzo.blit(capa, (x, 82 + round(20 * (1 - a))))


_PINTORES: dict[str, Pintor] = {
    "ciudad": _lamina_ciudad, "zonas": _lamina_zonas, "civitas": _lamina_civitas,
    "candidatos": _lamina_candidatos, "cierre": _lamina_cierre,
}


def _puntos(pantalla: pygame.Surface, tema: Tema, indice: int, total: int) -> None:
    """Indicador de progreso: un punto por lamina, el actual relleno."""
    x0 = ANCHO // 2 - (total - 1) * 12
    for i in range(total):
        centro = (x0 + i * 24, ALTO_ARTE - 12)
        pygame.draw.circle(pantalla, tema.acento if i == indice else tema.borde, centro, 6 if i == indice else 4)


def dibujar_intro(pantalla: pygame.Surface, lienzo: pygame.Surface, fuentes: Fuentes, tema: Tema,
                  intro: Intro, ciudad: GrafoCiudad, indice: int, t: float, alfa: float,
                  dialogo: CajaDialogo, pie: str) -> None:
    """Pinta la lamina `indice` en `lienzo` con opacidad `alfa` (0..255), y encima el subtitulo."""
    pantalla.fill(tema.fondo)
    lamina = intro.laminas[indice]
    _PINTORES[lamina.tipo](lienzo, fuentes, tema, intro, ciudad, lamina, t)
    lienzo.set_alpha(max(0, min(255, round(alfa))))
    pantalla.blit(lienzo, (0, 0))
    _puntos(pantalla, tema, indice, len(intro.laminas))
    dialogo.draw(pantalla, fuentes, tema)             # siempre opaco, nunca se desvanece
    pantalla.blit(fuentes.chica.render(pie, True, tema.texto), (24, pantalla.get_height() - 24))
