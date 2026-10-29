"""Vista: personajes en pixel art (los cuadros se construyen en views/pixel_sprites.py con los colores del tema)."""
import pygame

from post_truth.models.personaje import Personaje
from post_truth.views import pixel_sprites
from post_truth.views.theme import Tema


def dibujar_personaje(pantalla: pygame.Surface, personaje: Personaje, tema: Tema,
                      rect: pygame.Rect, animo: int = 0, sombra: bool = True) -> None:
    """Retrato de cuerpo entero (de frente, quieto) dentro de `rect`, apoyado en su borde inferior.
    Se amplia por un factor entero para que el pixel art quede nitido; `animo` cambia la boca."""
    escala = max(1, min(rect.width // pixel_sprites.ANCHO, rect.height // pixel_sprites.ALTO))
    img = pixel_sprites.cuadro_personaje(personaje, tema, "idle_abajo", 0, escala, animo)
    pies = (rect.centerx, rect.bottom)
    if sombra:
        ancho = pixel_sprites.ANCHO * escala
        pantalla.blit(pixel_sprites.sombra(ancho, max(2, 3 * escala)), (pies[0] - ancho // 2, pies[1] - 2 * escala))
    pantalla.blit(img, img.get_rect(midbottom=(pies[0], pies[1] + escala)))


def dibujar_personaje_mundo(pantalla: pygame.Surface, personaje: Personaje, tema: Tema, pies: tuple[int, int],
                            alto: int, nombre: str, cuadro: int) -> None:
    """Dibuja la animacion `nombre` en su `cuadro`, de unos `alto` pixeles y apoyada en `pies`."""
    escala = max(1, round(alto / pixel_sprites.ALTO))
    img = pixel_sprites.cuadro_personaje(personaje, tema, nombre, cuadro, escala)
    ancho = 10 * escala
    pantalla.blit(pixel_sprites.sombra(ancho, 3 * escala), (pies[0] - ancho // 2, pies[1] - 2 * escala))
    pantalla.blit(img, img.get_rect(midbottom=(pies[0], pies[1] + escala)))
