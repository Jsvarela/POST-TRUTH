"""Pantallas del multijugador (R12): conectar (nombre, IP y puerto) y sala de espera (jugadores y roles)."""
import math

import pygame

from post_truth.config import ANCHO, ALTO, px
from post_truth.views.componentes import Boton, Fuentes, Tarjeta, panel
from post_truth.views.fondo import dibujar_fondo_ciudad
from post_truth.views.theme import TOKENS, Tema, esp

RECT_CAJA = pygame.Rect(ANCHO // 2 - px(300), px(110), px(600), px(400))


def rect_campo(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_CAJA.x + esp(5), RECT_CAJA.y + px(96) + i * px(78), RECT_CAJA.w - 2 * esp(5), px(46))


def rect_boton_conectar() -> pygame.Rect:
    return pygame.Rect(RECT_CAJA.centerx - px(150), RECT_CAJA.bottom - px(92), px(300), px(54))


def rect_rol(i: int) -> pygame.Rect:
    return pygame.Rect(px(60), px(130) + i * px(76), px(300), px(60))


def rect_accion(i: int) -> pygame.Rect:
    return pygame.Rect(px(60), px(440) + i * px(58), px(300), px(48))


def _titulo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, titulo: str, sub: str) -> None:
    img = fuentes.titulo.render(titulo, True, tema.texto)
    pantalla.blit(img, img.get_rect(center=(ANCHO // 2, px(48))))
    img = fuentes.normal.render(sub, True, tema.acento)
    pantalla.blit(img, img.get_rect(center=(ANCHO // 2, px(88))))


def _pie(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, texto: str) -> None:
    img = fuentes.chica.render(texto, True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, ALTO - esp(3))))


def dibujar_conectar(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, campos: list[tuple[str, str]],
                     foco: int, aviso: tuple[str, str] | None, boton: Boton, t: float) -> None:
    """`campos`: (etiqueta, valor); el del foco lleva cursor que parpadea. `aviso`: (texto, tipo)."""
    dibujar_fondo_ciudad(pantalla, tema, t)
    _titulo(pantalla, fuentes, tema, "Multijugador", "Conectate al servidor de la partida (2 a 4 jugadores)")
    panel(pantalla, tema, RECT_CAJA, TOKENS.alfa_panel)
    for i, (etiqueta, valor) in enumerate(campos):
        r = rect_campo(i)
        pantalla.blit(fuentes.chica.render(etiqueta, True, tema.texto_off), (r.x, r.y - fuentes.chica.get_linesize()))
        activo = i == foco
        pygame.draw.rect(pantalla, tema.fondo, r, border_radius=px(TOKENS.radio_m))
        pygame.draw.rect(pantalla, tema.acento if activo else tema.borde, r, width=px(3 if activo else 2),
                         border_radius=px(TOKENS.radio_m))
        cursor = "|" if activo and math.sin(t * 6) > 0 else ""
        img = fuentes.normal.render(valor + cursor, True, tema.texto)
        pantalla.blit(img, img.get_rect(midleft=(r.x + esp(3), r.centery)))
    boton.draw(pantalla, fuentes.normal, tema)
    if aviso is not None:
        texto, tipo = aviso
        Tarjeta(pygame.Rect(RECT_CAJA.x, RECT_CAJA.bottom + esp(2), RECT_CAJA.w, px(80)), "Red", texto,
                tipo).draw(pantalla, fuentes, tema)
    _pie(pantalla, fuentes, tema, "Tab o flechas: cambiar de campo   |   Enter: conectar   |   ESC: volver al menu")


def dibujar_sala(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, filas: list[tuple[str, str, str]],
                 botones: list[Boton], aviso: tuple[str, str] | None, t: float) -> None:
    """`filas`: (titulo, texto, tipo) de cada jugador conectado, en orden de llegada (el primero es el anfitrion)."""
    dibujar_fondo_ciudad(pantalla, tema, t)
    _titulo(pantalla, fuentes, tema, "Sala de espera", "Cada jugador elige un rol distinto; los roles libres son aliados")
    caja = pygame.Rect(px(400), px(130), ANCHO - px(460), px(384))
    panel(pantalla, tema, caja, TOKENS.alfa_panel)
    pantalla.blit(fuentes.grande.render("Jugadores", True, tema.acento), (caja.x + esp(4), caja.y + esp(3)))
    for i, (titulo, texto, tipo) in enumerate(filas):
        Tarjeta(pygame.Rect(caja.x + esp(4), caja.y + px(52) + i * px(80), caja.w - 2 * esp(4), px(74)), titulo, texto,
                tipo).draw(pantalla, fuentes, tema)
    for b in botones:
        b.draw(pantalla, fuentes.normal, tema)
    if aviso is not None:
        Tarjeta(pygame.Rect(caja.x, caja.bottom + esp(2), caja.w, px(80)), "Red", aviso[0], aviso[1]).draw(
            pantalla, fuentes, tema)
    _pie(pantalla, fuentes, tema, "1-4: elegir rol   |   G: genero   |   Enter: iniciar (anfitrion)   |   ESC: salir")
