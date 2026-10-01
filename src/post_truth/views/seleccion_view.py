"""Vista de la seleccion de personaje: solo dibuja lo que el controlador le entrega."""
import pygame

from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Boton, Fuentes, Panel, dibujar_texto_ajustado
from post_truth.views.personaje_view import dibujar_personaje
from post_truth.views.theme import Tema


def dibujar_seleccion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, titulo: str,
                      subtitulo: str, paneles: list[Panel],
                      personajes: list[tuple[Personaje, pygame.Rect]],
                      descripcion: tuple[pygame.Rect, str] | None,
                      botones: list[Boton], pie: str) -> None:
    pantalla.fill(tema.fondo)
    img = fuentes.titulo.render(titulo, True, tema.texto)
    pantalla.blit(img, img.get_rect(center=(pantalla.get_width() // 2, 48)))
    sub = fuentes.normal.render(subtitulo, True, tema.acento)
    pantalla.blit(sub, sub.get_rect(center=(pantalla.get_width() // 2, 92)))
    for panel in paneles:
        panel.draw(pantalla, fuentes, tema)
    for personaje, rect in personajes:
        dibujar_personaje(pantalla, personaje, tema, rect)
    if descripcion:
        rect, texto = descripcion
        dibujar_texto_ajustado(pantalla, fuentes.normal, texto, tema.texto, rect)
    for boton in botones:
        boton.draw(pantalla, fuentes.normal, tema)
    pantalla.blit(fuentes.chica.render(pie, True, tema.texto), (30, pantalla.get_height() - 28))
