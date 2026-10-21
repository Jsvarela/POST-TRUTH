"""Proveedor de arte del mundo caminable: todo dibujado con formas y colores del tema."""
import math

import pygame

from post_truth.config import px
from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Fuentes
from post_truth.views.mapa_view import _icono_zona
from post_truth.views.personaje_view import dibujar_personaje_mundo
from post_truth.views.theme import Tema

Punto = tuple[int, int]


def _mezclar(a: tuple[int, int, int], b: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    """Tono intermedio entre dos colores del tema."""
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


class ArteFormas:
    def suelo(self, pantalla: pygame.Surface, tema: Tema) -> None:
        pantalla.fill(tema.suelo)

    def calle(self, pantalla: pygame.Surface, tema: Tema, a: Punto, b: Punto, ancho: int) -> None:
        for color, grosor in ((tema.borde, ancho + px(6)), (tema.panel, ancho)):
            pygame.draw.line(pantalla, color, a, b, grosor)
            for extremo in (a, b):
                pygame.draw.circle(pantalla, color, extremo, grosor // 2)

    def plaza(self, pantalla: pygame.Surface, tema: Tema, centro: Punto, radio: int) -> None:
        pygame.draw.circle(pantalla, tema.borde, centro, radio + px(3))
        pygame.draw.circle(pantalla, tema.panel, centro, radio)
        pygame.draw.circle(pantalla, tema.borde, centro, max(1, radio * 2 // 3), px(2))

    def edificio(self, pantalla: pygame.Surface, tema: Tema, fuentes: Fuentes, zona: str, nombre: str,
                 rect: pygame.Rect, resaltado: bool, t: float = 0.0) -> None:
        pygame.draw.rect(pantalla, tema.edificio, rect, border_radius=px(10))
        techo = pygame.Rect(rect.x, rect.y, rect.w, rect.h // 7)
        pygame.draw.rect(pantalla, _mezclar(tema.edificio, tema.fondo, 0.45), techo,
                         border_top_left_radius=px(10), border_top_right_radius=px(10))
        tam = max(3, rect.w // 11)
        for i, (fx, fy) in enumerate(((0.1, 0.3), (0.1, 0.55), (0.78, 0.3), (0.78, 0.55))):
            luz = (i * 7 + int(t / 2.5 + i * 0.37) + len(zona)) % 3 != 0
            ventana = pygame.Rect(rect.x + round(rect.w * fx), rect.y + round(rect.h * fy), tam, round(tam * 1.3))
            pygame.draw.rect(pantalla, tema.detalle if luz else _mezclar(tema.edificio, tema.fondo, 0.6), ventana,
                             border_radius=px(2))
        pygame.draw.rect(pantalla, tema.acento if resaltado else tema.borde, rect, px(5) if resaltado else px(2),
                         border_radius=px(10))
        _icono_zona(pantalla, tema, zona, (rect.centerx, rect.centery - px(10)), min(rect.w, rect.h) * 3 // 10,
                    nombre, fuentes.normal)
        img = fuentes.chica.render(nombre, True, tema.texto)
        pantalla.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom - px(6))))

    def cesped(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int, variante: int) -> None:
        color = _mezclar(tema.suelo, tema.verde, 0.35 + 0.15 * variante)
        x, y = pos
        for dx, alto in ((-tam // 2, tam), (0, tam + tam // 3), (tam // 2, tam)):
            pygame.draw.line(pantalla, color, (x + dx, y), (x + dx + dx // 2, y - alto), max(1, tam // 4))

    def arbusto(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int, flores: bool) -> None:
        x, y = pos
        pygame.draw.ellipse(pantalla, _mezclar(tema.suelo, tema.fondo, 0.5), (x - tam, y - tam // 4, tam * 2, tam // 2))
        for dx, r in ((-tam // 2, tam * 2 // 3), (tam // 2, tam * 2 // 3), (0, tam)):
            pygame.draw.circle(pantalla, _mezclar(tema.verde, tema.fondo, 0.2), (x + dx, y - r // 2), r)
        if flores:
            for dx, dy in ((-tam // 2, -tam // 2), (tam // 3, -tam), (tam // 2, -tam // 3)):
                pygame.draw.circle(pantalla, tema.detalle, (x + dx, y + dy), max(2, tam // 5))

    def arbol(self, pantalla: pygame.Surface, tema: Tema, base: Punto, tam: int, balanceo: float) -> None:
        """`balanceo` mueve la copa con el viento."""
        x, y = base
        pygame.draw.ellipse(pantalla, _mezclar(tema.suelo, tema.fondo, 0.55), (x - tam, y - tam // 4, tam * 2, tam // 2))
        pygame.draw.rect(pantalla, _mezclar(tema.edificio, tema.fondo, 0.35), (x - tam // 6, y - tam, tam // 3, tam),
                         border_radius=max(1, tam // 10))
        cx, cy = x + round(balanceo * tam * 0.12), y - tam - tam // 3
        oscuro, claro = _mezclar(tema.verde, tema.fondo, 0.3), _mezclar(tema.verde, tema.texto, 0.2)
        for dx, dy, r, color in ((-tam // 3, tam // 6, tam * 2 // 3, oscuro), (tam // 3, tam // 6, tam * 2 // 3, oscuro),
                                 (0, -tam // 5, tam * 3 // 4, tema.verde), (-tam // 6, -tam // 3, tam // 3, claro)):
            pygame.draw.circle(pantalla, color, (cx + dx, cy + dy), r)

    def farol(self, pantalla: pygame.Surface, tema: Tema, base: Punto, tam: int, brillo: float) -> None:
        """`brillo` late despacio: el halo es semitransparente."""
        x, y = base
        lampara = (x, y - tam)
        halo = tam // 3 + round(brillo * tam // 10)
        capa = pygame.Surface((halo * 2, halo * 2), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*tema.detalle, 22 + round(26 * brillo)), (halo, halo), halo)
        pantalla.blit(capa, (lampara[0] - halo, lampara[1] - halo))
        pygame.draw.line(pantalla, tema.borde, (x, y), lampara, max(2, tam // 12))
        pygame.draw.circle(pantalla, tema.detalle, lampara, max(2, tam // 8))

    def banca(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int) -> None:
        x, y = pos
        madera = _mezclar(tema.edificio, tema.detalle, 0.25)
        for dx in (-tam // 2 + 2, tam // 2 - 4):
            pygame.draw.line(pantalla, tema.borde, (x + dx, y), (x + dx, y + tam // 3), max(1, tam // 10))
        pygame.draw.rect(pantalla, madera, (x - tam // 2, y - tam // 6, tam, tam // 4), border_radius=max(1, tam // 10))
        pygame.draw.rect(pantalla, madera, (x - tam // 2, y - tam // 2, tam, tam // 6), border_radius=max(1, tam // 10))

    def pajaro(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int, aleteo: float) -> None:
        """Una "v" que bate las alas."""
        x, y = pos
        ala = round(aleteo * tam * 0.6)
        pygame.draw.lines(pantalla, tema.texto, False, [(x - tam, y - ala), (x, y), (x + tam, y - ala)], max(1, tam // 5))

    def personaje(self, pantalla: pygame.Surface, tema: Tema, pies: Punto, alto: int, personaje: Personaje,
                  animacion: str, cuadro: int) -> None:
        """`animacion` y `cuadro` son la fila y la columna de la futura hoja de sprites."""
        dibujar_personaje_mundo(pantalla, personaje, tema, pies, alto, animacion, cuadro)


ARTE_FORMAS = ArteFormas()
