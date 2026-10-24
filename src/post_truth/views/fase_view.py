"""Pantalla de transicion de fase: anuncia la fase nueva y lo que cambio en la ciudad, con entrada animada."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.fases import Fase
from post_truth.views.anuncio_view import _icono, _rebote
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.theme import Tema


def dibujar_fase(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, numero: int, total: int, fase: Fase,
                 cambios: list[tuple[str, str]], t: float) -> None:
    pantalla.fill(tema.fondo)
    entrada = min(1.0, t / 0.4)
    escala = max(0.05, _rebote(entrada))
    titulo = fuentes.titulo.render(f"Fase {numero} de {total}: {fase.nombre}", True, tema.acento)
    titulo = pygame.transform.smoothscale(titulo, (max(1, round(titulo.get_width() * escala)),
                                                   max(1, round(titulo.get_height() * escala))))
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(70))))
    y = px(150)
    for linea in ajustar_texto(fase.descripcion, fuentes.normal, px(760)):
        img = fuentes.normal.render(linea, True, tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(ANCHO // 2, y)))
        y += fuentes.normal.get_linesize()
    caja = pygame.Rect(px(130), y + px(20), px(764), px(300))
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(12))
    pantalla.blit(fuentes.normal.render("Asi cambio la ciudad", True, tema.acento), (caja.x + px(16), caja.y + px(12)))
    fila = caja.y + px(54)
    for i, (tipo, texto) in enumerate(cambios or [("info", "La ciudad sigue igual que ayer.")]):
        if t < 0.4 + 0.25 * i:      # cada cambio aparece un poco despues del anterior
            break
        _icono(pantalla, tema, tipo, (caja.x + px(30), fila + px(12)), px(12), 0)
        for linea in ajustar_texto(texto, fuentes.chica, caja.w - px(70))[:2]:
            pantalla.blit(fuentes.chica.render(linea, True, tema.texto), (caja.x + px(52), fila))
            fila += fuentes.chica.get_linesize()
        fila += px(10)
        if fila > caja.bottom - px(30):
            break
    ayuda = fuentes.normal.render("Enter: empezar el dia", True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(30))))
