"""Vista del menu principal: la ciudad de fondo, el titulo, los botones y el panel de opciones. Solo dibuja."""
import math

import pygame

from post_truth.config import ANCHO, ALTO, px
from post_truth.views.componentes import Boton, Fuentes, panel
from post_truth.views.fondo import dibujar_fondo_ciudad
from post_truth.views.theme import TOKENS, Tema, esp


def rect_boton(i: int) -> pygame.Rect:
    return pygame.Rect(ANCHO // 2 - px(170), px(262) + i * px(58), px(340), px(50))


RECT_OPCIONES = pygame.Rect(ANCHO // 2 - px(260), px(110), px(520), px(480))


def rect_opcion(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_OPCIONES.x + esp(4), RECT_OPCIONES.y + px(64) + i * px(54), RECT_OPCIONES.w - 2 * esp(4),
                       px(44))


def dibujar_menu(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, botones: list[Boton], t: float,
                 opciones: list[tuple[str, str]] | None = None, fila: int = 0) -> None:
    dibujar_fondo_ciudad(pantalla, tema, t)
    entrada = min(1.0, t / TOKENS.dur_lenta)
    desliza = round(px(40) * (1 - entrada) ** 2)      # el titulo baja suave al abrir
    titulo = fuentes.enorme.render("POST & TRUTH", True, tema.texto)
    centro = (ANCHO // 2, px(130) - desliza)
    pantalla.blit(fuentes.enorme.render("POST & TRUTH", True, tema.fondo), titulo.get_rect(center=centro).move(px(4), px(4)))
    pantalla.blit(titulo, titulo.get_rect(center=centro))
    ancho_linea = round(titulo.get_width() * entrada * (0.9 + 0.1 * math.sin(t * 2)))
    pygame.draw.rect(pantalla, tema.acento, (ANCHO // 2 - ancho_linea // 2, centro[1] + titulo.get_height() // 2,
                                             ancho_linea, px(6)), border_radius=px(3))
    sub = fuentes.normal.render("Alcalde Digital  -  Ciudad Nova elige alcalde en 4 dias", True, tema.acento)
    pantalla.blit(sub, sub.get_rect(center=(ANCHO // 2, centro[1] + titulo.get_height() // 2 + px(36))))
    for i, b in enumerate(botones):   # entran uno tras otro
        if t >= 0.08 * i:
            b.draw(pantalla, fuentes.normal, tema)
    ayuda = fuentes.chica.render("Flechas y Enter, o clic   |   atajos: A ayuda, R multijugador, I intro, T tema, X tiempo, O opciones",
                                 True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midbottom=(ANCHO // 2, ALTO - esp(4))))
    if opciones is not None:
        velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
        velo.fill((*tema.fondo, TOKENS.alfa_velo))
        pantalla.blit(velo, (0, 0))
        panel(pantalla, tema, RECT_OPCIONES, 255, borde=tema.acento)
        pantalla.blit(fuentes.grande.render("Opciones", True, tema.acento), (RECT_OPCIONES.x + esp(4), RECT_OPCIONES.y + esp(3)))
        for i, (nombre, valor) in enumerate(opciones):
            r = rect_opcion(i)
            b = Boton(r, "", lambda: None)
            b.foco = i == fila
            b.draw(pantalla, fuentes.normal, tema)
            pantalla.blit(fuentes.normal.render(nombre, True, tema.boton_texto), (r.x + esp(3), r.y + px(8)))
            img = fuentes.normal.render(valor, True, tema.boton_texto)
            pantalla.blit(img, img.get_rect(midright=(r.right - esp(3), r.centery)))
        ayuda = fuentes.chica.render("Flechas: elegir y cambiar   |   Enter o ESC: cerrar", True, tema.texto)
        pantalla.blit(ayuda, ayuda.get_rect(midbottom=(RECT_OPCIONES.centerx, RECT_OPCIONES.bottom - esp(2))))
