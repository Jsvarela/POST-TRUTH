"""Proveedor de arte de la capa dinamica del mundo (lo que se mueve sobre mapa.png): formas y colores del tema."""
import pygame

from post_truth.config import px
from post_truth.models.personaje import Personaje
from post_truth.views import pixel_sprites
from post_truth.views.personaje_view import dibujar_personaje_mundo
from post_truth.views.theme import Tema, mezclar

Punto = tuple[int, int]


class ArteFormas:
    def arbusto(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int, flores: bool) -> None:
        x, y = pos
        pygame.draw.ellipse(pantalla, mezclar(tema.suelo, tema.fondo, 0.5), (x - tam, y - tam // 4, tam * 2, tam // 2))
        for dx, r in ((-tam // 2, tam * 2 // 3), (tam // 2, tam * 2 // 3), (0, tam)):
            pygame.draw.circle(pantalla, mezclar(tema.verde, tema.fondo, 0.2), (x + dx, y - r // 2), r)
        if flores:
            for dx, dy in ((-tam // 2, -tam // 2), (tam // 3, -tam), (tam // 2, -tam // 3)):
                pygame.draw.circle(pantalla, tema.detalle, (x + dx, y + dy), max(2, tam // 5))

    def arbol(self, pantalla: pygame.Surface, tema: Tema, base: Punto, tam: int, balanceo: float) -> None:
        """`balanceo` mueve la copa con el viento."""
        x, y = base
        pygame.draw.ellipse(pantalla, mezclar(tema.suelo, tema.fondo, 0.55), (x - tam, y - tam // 4, tam * 2, tam // 2))
        pygame.draw.rect(pantalla, mezclar(tema.edificio, tema.fondo, 0.35), (x - tam // 6, y - tam, tam // 3, tam),
                         border_radius=max(1, tam // 10))
        cx, cy = x + round(balanceo * tam * 0.12), y - tam - tam // 3
        oscuro, claro = mezclar(tema.verde, tema.fondo, 0.3), mezclar(tema.verde, tema.texto, 0.2)
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
        madera = mezclar(tema.edificio, tema.detalle, 0.25)
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


class ArtePixel(ArteFormas):
    """Mismo contrato que ArteFormas, con los sprites pixel art de views/pixel_sprites.py."""

    @staticmethod
    def _escala() -> int:
        return max(1, round(px(2)))   # un pixel de arte = 2 pixeles del mapa, igual que mapa.png

    def arbusto(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int, flores: bool) -> None:
        img = pixel_sprites.arbusto(flores, self._escala())
        pantalla.blit(pixel_sprites.sombra(img.get_width(), img.get_height() // 3), img.get_rect(
            center=(pos[0], pos[1])).move(0, img.get_height() // 3))
        pantalla.blit(img, img.get_rect(midbottom=(pos[0], pos[1] + img.get_height() // 3)))

    def arbol(self, pantalla: pygame.Surface, tema: Tema, base: Punto, tam: int, balanceo: float) -> None:
        e = self._escala()
        variante = round(tam / max(1, px(1))) % 3
        mover = 1 if balanceo > 0.7 else -1 if balanceo < -0.7 else 0
        img = pixel_sprites.arbol(variante, mover, e)
        ancho = img.get_width() * 3 // 4
        pantalla.blit(pixel_sprites.sombra(ancho, ancho // 3, 80), (base[0] - ancho // 2, base[1] - ancho // 6))
        pantalla.blit(img, img.get_rect(midbottom=(base[0], base[1] + 3 * e)))

    def farol(self, pantalla: pygame.Surface, tema: Tema, base: Punto, tam: int, brillo: float) -> None:
        e = self._escala()
        img = pixel_sprites.farol(brillo > 0.35, e)
        rect = img.get_rect(midbottom=(base[0], base[1] + e))
        if brillo > 0.35:
            halo = 7 * e + round(brillo * 2 * e)
            capa = pygame.Surface((halo * 2, halo * 2), pygame.SRCALPHA)
            pygame.draw.circle(capa, (255, 226, 150, 26 + round(30 * brillo)), (halo, halo), halo)
            pygame.draw.circle(capa, (255, 236, 180, 30 + round(30 * brillo)), (halo, halo), halo // 2)
            pantalla.blit(capa, (rect.centerx - halo, rect.y + 3 * e - halo))
        pantalla.blit(img, rect)

    def banca(self, pantalla: pygame.Surface, tema: Tema, pos: Punto, tam: int) -> None:
        img = pixel_sprites.banca(self._escala())
        pantalla.blit(img, img.get_rect(center=pos))

    def personaje(self, pantalla: pygame.Surface, tema: Tema, pies: Punto, alto: int, personaje: Personaje,
                  animacion: str, cuadro: int) -> None:
        dibujar_personaje_mundo(pantalla, personaje, tema, pies, alto, animacion, cuadro)


ARTE_FORMAS = ArteFormas()
ARTE_PIXEL = ArtePixel()
