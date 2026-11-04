"""Vista: retratos con el sprite pixel del personaje, en un marco pixel (L5: reemplaza el busto vectorial)."""
import pygame

from post_truth.config import px
from post_truth.models.personaje import Personaje
from post_truth.views.arte_mundo import ARTE_PIXEL
from post_truth.views.componentes import marco_pixel
from post_truth.views.theme import Tema


def dibujar_retrato(pantalla: pygame.Surface, personaje: Personaje, tema: Tema, rect: pygame.Rect,
                    fondo=None, borde=None) -> None:
    marco_pixel(pantalla, tema, rect, relleno=fondo, borde=borde)
    margen = max(px(4), rect.h // 10)
    ARTE_PIXEL.personaje(pantalla, tema, (rect.centerx, rect.bottom - margen), rect.h - 2 * margen, personaje,
                         "idle_abajo", 0)
