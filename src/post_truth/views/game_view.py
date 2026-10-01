"""Vista del juego: dibuja indicadores, publicacion y opciones a partir de datos del modelo."""
import pygame
from post_truth.views.theme import Tema

# Indicadores donde subir es malo: se pintan con el color de peligro del tema.
NEGATIVOS = {"Desinformacion", "Conflictos"}


def dibujar_juego(pantalla: pygame.Surface, fuente: pygame.font.Font, tema: Tema,
                  filas: list[tuple[str, int]], titulo: str, contenido: str,
                  opciones: list[str], feedback: str) -> None:
    pantalla.fill(tema.fondo)
    y = 20
    for nombre, valor in filas:
        pantalla.blit(fuente.render(f"{nombre}: {valor}", True, tema.texto), (40, y))
        # El puntaje no es un indicador 0-100: se muestra solo como texto.
        if not nombre.startswith("Puntaje"):
            pygame.draw.rect(pantalla, tema.panel, (330, y + 4, 300, 18))
            color = tema.malo if nombre in NEGATIVOS else tema.bueno
            pygame.draw.rect(pantalla, color, (330, y + 4, 3 * valor, 18))
        y += 32
    pantalla.blit(fuente.render(titulo, True, tema.acento), (40, 270))
    pantalla.blit(fuente.render(contenido, True, tema.texto), (40, 310))
    for i, txt in enumerate(opciones):
        pantalla.blit(fuente.render(f"{i + 1}  {txt}", True, tema.texto), (40, 370 + i * 36))
    if feedback:
        pantalla.blit(fuente.render(feedback, True, tema.acento), (40, 540))
    pantalla.blit(fuente.render("ESC menu", True, tema.acento), (40, 590))
