"""Vista del mundo caminable: camara que sigue al jugador y dibujo a traves de un proveedor de arte.

El mundo (data/mundo.json) es mas grande que la pantalla: se ve una ventana de ANCHO/ESCALA x ALTO/ESCALA
pixeles del mundo alrededor del jugador, y la camara se detiene en los bordes del mundo.
"""
import pygame

from post_truth.config import ALTO, ANCHO, ESCALA, px
from post_truth.models.mundo import MundoCiudad
from post_truth.views.arte_mundo import ARTE_FORMAS, ArteFormas
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import Tema

AYUDA = "Caminar: WASD o flechas   |   E: entrar   |   ESC: menu"


def camara(mundo: MundoCiudad, ancho: int = ANCHO, alto: int = ALTO) -> tuple[float, float]:
    """Esquina superior izquierda (en pixeles del mundo) de lo que se ve: centrada en el jugador y sin salirse
    del mundo. Si el mundo es mas chico que la pantalla en un eje, se centra en ese eje."""
    vista_w, vista_h = ancho / ESCALA, alto / ESCALA
    mundo_w, mundo_h = mundo.tamano

    def eje(jugador: float, vista: float, total: float) -> float:
        if total <= vista:
            return (total - vista) / 2
        return min(max(jugador - vista / 2, 0.0), total - vista)
    return eje(mundo.jugador[0], vista_w, mundo_w), eje(mundo.jugador[1], vista_h, mundo_h)


def a_pantalla(p: tuple[float, float], cam: tuple[float, float]) -> tuple[int, int]:
    return px(p[0] - cam[0]), px(p[1] - cam[1])


def dibujar_mundo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MundoCiudad, color_rol: int = 0,
                  aviso: str = "", arte: ArteFormas = ARTE_FORMAS) -> None:
    cam = camara(mundo, *pantalla.get_size())
    arte.suelo(pantalla, tema)
    for c in mundo.calles:
        arte.calle(pantalla, tema, a_pantalla(mundo.plazas[c.desde].pos, cam), a_pantalla(mundo.plazas[c.hasta].pos, cam),
                   px(c.ancho))
    for p in mundo.plazas.values():
        arte.plaza(pantalla, tema, a_pantalla(p.pos, cam), px(p.radio))
    alcance = mundo.zona_al_alcance()
    for e in mundo.edificios:
        x, y, w, h = e.rect
        rect = pygame.Rect(*a_pantalla((x, y), cam), px(w), px(h))
        if rect.colliderect(pantalla.get_rect()):
            arte.edificio(pantalla, tema, fuentes, e.zona, e.zona.capitalize(), rect, e.zona == alcance)
    arte.personaje(pantalla, tema, a_pantalla(mundo.jugador, cam), px(mundo.radio_jugador), color_rol)
    _franja(pantalla, fuentes, tema, aviso or (f"E: entrar a {alcance.capitalize()}" if alcance else ""))


def _franja(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mensaje: str) -> None:
    """Franja inferior: el mensaje del momento (o que lugar esta al alcance) y los controles."""
    ancho, alto = pantalla.get_size()
    caja = pygame.Rect(px(16), alto - px(70), ancho - px(32), px(56))
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(12))
    if mensaje:
        img = fuentes.normal.render(mensaje, True, tema.acento)
        pantalla.blit(img, img.get_rect(midleft=(caja.x + px(18), caja.centery)))
    ayuda = fuentes.chica.render(AYUDA, True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midright=(caja.right - px(18), caja.centery)))
