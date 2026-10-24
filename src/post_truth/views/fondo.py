"""Fondo de las pantallas fuera del juego (menu, seleccion, fase): la ciudad desplazandose despacio bajo un velo."""
import json
import math

import pygame

from post_truth.config import RUTA_MAPA
from post_truth.mapa_abierto import RAIZ
from post_truth.views.theme import TOKENS, Tema

_IMAGEN: dict[tuple[int, int], pygame.Surface] = {}
VELOCIDAD = 14.0   # pixeles por segundo


def _ciudad(ancho: int, alto: int) -> pygame.Surface:
    """mapa.png escalado para cubrir la pantalla con un 25% de sobra para desplazarse (una vez por tamano)."""
    if (ancho, alto) not in _IMAGEN:
        ruta = RAIZ / json.loads(RUTA_MAPA.read_text(encoding="utf-8"))["imagenes"]["mapa"]
        img = pygame.image.load(str(ruta)).convert()
        f = 1.25 * max(ancho / img.get_width(), alto / img.get_height())
        _IMAGEN[(ancho, alto)] = pygame.transform.smoothscale(img, (round(img.get_width() * f),
                                                                    round(img.get_height() * f)))
    return _IMAGEN[(ancho, alto)]


def dibujar_fondo_ciudad(pantalla: pygame.Surface, tema: Tema, t: float) -> None:
    ancho, alto = pantalla.get_size()
    ciudad = _ciudad(ancho, alto)
    recorrido = max(1, ciudad.get_width() - ancho)
    x = recorrido * (0.5 - 0.5 * math.cos(t * VELOCIDAD / recorrido * math.pi))   # va y vuelve, sin saltos
    y = (ciudad.get_height() - alto) // 2
    pantalla.blit(ciudad, (0, 0), pygame.Rect(round(x), y, ancho, alto))
    velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    velo.fill((*tema.fondo, TOKENS.alfa_velo + 40))
    pantalla.blit(velo, (0, 0))
