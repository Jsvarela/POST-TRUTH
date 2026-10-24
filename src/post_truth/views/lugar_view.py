"""Interior de un lugar: lo primero al entrar. Muestra lo que se encontro y que se puede hacer ahi."""
import pygame

from post_truth.config import ALTO, ANCHO, px
from post_truth.views.componentes import Boton, Fuentes, Tarjeta, panel
from post_truth.views.escena_view import RECT_ESCENA
from post_truth.views.theme import TOKENS, Tema, esp
from post_truth.views.zona_view import dibujar_fondo_zona

RECT_PANEL = pygame.Rect(ANCHO // 2 - px(330), px(110), px(660), px(470))


def rect_boton(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_PANEL.x + esp(4), RECT_PANEL.y + px(268) + i * px(58), RECT_PANEL.w - 2 * esp(4), px(48))


def dibujar_lugar(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, zona: str, nombre: str,
                  tarjetas: list[tuple[str, str, str]], botones: list[Boton], t: float) -> None:
    """`tarjetas`: (titulo, texto, tipo) de lo que hay aqui (evidencia hallada, la noticia del dia...)."""
    pantalla.fill(tema.fondo)
    dibujar_fondo_zona(pantalla, zona, tema, pygame.Rect(0, RECT_ESCENA.y, ANCHO, ALTO - RECT_ESCENA.y))
    entrada = min(1.0, t / TOKENS.dur_media)
    caja = RECT_PANEL.move(0, round(px(30) * (1 - entrada) ** 2))   # el panel sube suave al entrar
    panel(pantalla, tema, caja, TOKENS.alfa_panel)
    titulo = fuentes.titulo.render(nombre, True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(caja.centerx, caja.y + esp(3))))
    y = caja.y + px(80)
    for titulo_t, texto, tipo in tarjetas[:2]:
        Tarjeta(pygame.Rect(caja.x + esp(4), y, caja.w - 2 * esp(4), px(84)), titulo_t, texto, tipo).draw(
            pantalla, fuentes, tema)
        y += px(92)
    for b in botones:
        b.draw(pantalla, fuentes.normal, tema)
    ayuda = fuentes.chica.render("1-3 o clic: elegir   |   Enter: lo primero   |   ESC: volver a la calle", True,
                                 tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midbottom=(ANCHO // 2, ALTO - esp(3))))
