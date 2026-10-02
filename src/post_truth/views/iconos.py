"""Iconos pequenos dibujados con formas de Pygame, compartidos por varias vistas.

El mismo icono significa lo mismo en todas partes: el RAYO es energia (HUD, costo de una pista de la
tarjeta, costo de un viaje en el mapa). Los colores los pone quien llama (siempre del tema).
"""
import pygame

# Rayo: zigzag normalizado a una caja de -1..1; se escala con el tamano pedido.
_RAYO = [(0.15, -1.0), (-0.55, 0.12), (-0.08, 0.12), (-0.28, 1.0), (0.55, -0.22), (0.08, -0.22), (0.42, -1.0)]


def rayo(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int], tam: int,
         lleno: bool = True) -> None:
    """Rayo de energia de alto `2 * tam`: relleno si la energia esta disponible, solo contorno si se gasto."""
    cx, cy = centro
    puntos = [(cx + x * tam * 0.62, cy + y * tam) for x, y in _RAYO]
    if lleno:
        pygame.draw.polygon(pantalla, color, puntos)
    else:
        pygame.draw.polygon(pantalla, color, puntos, max(1, tam // 5))


def fila_de_rayos(pantalla: pygame.Surface, color: tuple[int, int, int], izquierda: int, centro_y: int, cantidad: int,
                  tam: int, separacion: int, llenos: int | None = None) -> int:
    """Dibuja `cantidad` rayos en fila (los primeros `llenos` rellenos). Devuelve el x donde termina la fila."""
    llenos = cantidad if llenos is None else llenos
    for i in range(cantidad):
        rayo(pantalla, color, (izquierda + i * separacion, centro_y), tam, lleno=i < llenos)
    return izquierda + max(0, cantidad - 1) * separacion + tam
