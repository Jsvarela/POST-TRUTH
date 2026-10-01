"""Vista del menu: solo dibuja, no decide nada."""
import pygame
from post_truth.views.theme import Tema


def dibujar_menu(pantalla: pygame.Surface, fuente: pygame.font.Font, tema: Tema) -> None:
    pantalla.fill(tema.fondo)
    lineas = ["POST & TRUTH", "ENTER: jugar", "I: ver la introduccion", "T: cambiar tema (accesibilidad)", "ESC: salir"]
    for i, txt in enumerate(lineas):
        color = tema.acento if i == 0 else tema.texto
        img = fuente.render(txt, True, color)
        pantalla.blit(img, img.get_rect(center=(pantalla.get_width() // 2, 200 + i * 50)))
