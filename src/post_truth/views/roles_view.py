"""HUD de la habilidad del rol y menu rapido de aliados (recarga en texto y en barra, no solo color)."""
import math

import pygame

from post_truth.config import ANCHO, ALTO, px
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import Tema


def dibujar_habilidad(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                      habilidad: tuple[str, float, float]) -> None:
    nombre, falta, total = habilidad
    pygame.draw.rect(pantalla, tema.panel, rect)
    if falta > 0:   # la barra se llena mientras recarga
        lleno = round(rect.w * (1 - falta / total))
        pygame.draw.rect(pantalla, tema.boton_off, (rect.x, rect.y, lleno, rect.h))
    pygame.draw.rect(pantalla, tema.acento if falta == 0 else tema.borde, rect, px(2))
    pantalla.blit(fuentes.chica.render(f"H: {nombre}", True, tema.texto), (rect.x + px(10), rect.y + px(4)))
    estado = "Lista" if falta == 0 else f"Recarga {math.ceil(falta)} s"
    pantalla.blit(fuentes.chica.render(estado, True, tema.acento if falta == 0 else tema.texto_off),
                  (rect.x + px(10), rect.y + px(24)))


def dibujar_menu_aliados(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, filas: list[tuple[str, float]]) -> None:
    alto = px(46) + len(filas) * px(32)
    caja = pygame.Rect(0, 0, px(520), alto)
    caja.midbottom = (ANCHO // 2, ALTO - px(130))
    pygame.draw.rect(pantalla, tema.panel, caja)
    pygame.draw.rect(pantalla, tema.acento, caja, px(2))
    pantalla.blit(fuentes.normal.render("Pide ayuda a tus aliados (Y cierra)", True, tema.acento),
                  (caja.x + px(14), caja.y + px(8)))
    for i, (texto, falta) in enumerate(filas):
        y = caja.y + px(42) + i * px(32)
        listo = falta == 0
        color = tema.texto if listo else tema.texto_off
        pantalla.blit(fuentes.chica.render(f"{i + 1}. {texto}", True, color), (caja.x + px(14), y))
        estado = fuentes.chica.render("listo" if listo else f"{math.ceil(falta)} s", True,
                                      tema.acento if listo else tema.texto_off)
        pantalla.blit(estado, estado.get_rect(topright=(caja.right - px(14), y)))
