"""Proveedor de arte del mundo caminable: todo dibujado con formas y colores del tema.

La vista (mundo_view) nunca dibuja el mundo directamente: le pide cada pieza al proveedor, ya en coordenadas
de PANTALLA. Para pasar a tilesets o sprites PNG basta con otra clase con los mismos metodos (por ejemplo un
ArtePNG que haga blit de imagenes de assets/) y pasarla a `dibujar_mundo`; el modelo y la vista no cambian.
"""
import pygame

from post_truth.config import px
from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Fuentes
from post_truth.views.mapa_view import _icono_zona
from post_truth.views.personaje_view import dibujar_personaje_mundo
from post_truth.views.theme import Tema

Punto = tuple[int, int]


class ArteFormas:
    def suelo(self, pantalla: pygame.Surface, tema: Tema) -> None:
        pantalla.fill(tema.suelo)

    def calle(self, pantalla: pygame.Surface, tema: Tema, a: Punto, b: Punto, ancho: int) -> None:
        # Una calle es una capsula: linea gruesa con extremos redondos (se une limpio con las plazas)
        for color, grosor in ((tema.borde, ancho + px(6)), (tema.panel, ancho)):
            pygame.draw.line(pantalla, color, a, b, grosor)
            for extremo in (a, b):
                pygame.draw.circle(pantalla, color, extremo, grosor // 2)

    def plaza(self, pantalla: pygame.Surface, tema: Tema, centro: Punto, radio: int) -> None:
        pygame.draw.circle(pantalla, tema.borde, centro, radio + px(3))
        pygame.draw.circle(pantalla, tema.panel, centro, radio)
        pygame.draw.circle(pantalla, tema.borde, centro, max(1, radio * 2 // 3), px(2))   # baldosas

    def edificio(self, pantalla: pygame.Surface, tema: Tema, fuentes: Fuentes, zona: str, nombre: str,
                 rect: pygame.Rect, resaltado: bool) -> None:
        pygame.draw.rect(pantalla, tema.edificio, rect, border_radius=px(10))
        pygame.draw.rect(pantalla, tema.acento if resaltado else tema.borde, rect, px(5) if resaltado else px(2),
                         border_radius=px(10))
        _icono_zona(pantalla, tema, zona, (rect.centerx, rect.centery - px(10)), min(rect.w, rect.h) * 3 // 10,
                    nombre, fuentes.normal)
        img = fuentes.chica.render(nombre, True, tema.texto)
        pantalla.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom - px(6))))

    def personaje(self, pantalla: pygame.Surface, tema: Tema, pies: Punto, alto: int, personaje: Personaje,
                  animacion: str, cuadro: int) -> None:
        """`animacion` y `cuadro` son la fila y la columna de la futura hoja de sprites (models/animacion.py)."""
        dibujar_personaje_mundo(pantalla, personaje, tema, pies, alto, animacion, cuadro)


ARTE_FORMAS = ArteFormas()
