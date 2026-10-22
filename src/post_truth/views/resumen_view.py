"""Vista del resumen del dia de campana: lo que cambio en la ciudad y lo que se decidio."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models import Impact
from post_truth.views.componentes import Fuentes
from post_truth.views.escena_view import _dibujar_consecuencias, _dibujar_hud
from post_truth.views.theme import Tema


def dibujar_resumen(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, dia: int, total: int,
                    filas: list[tuple[str, int]], cambio: Impact, decisiones: list[tuple[str, str, int]],
                    credibilidad: int, cambio_credibilidad: int) -> None:
    """`decisiones`: (titulo, accion, cambio de credibilidad que dejo)."""
    pantalla.fill(tema.fondo)
    _dibujar_hud(pantalla, fuentes, tema, filas, credibilidad)
    titulo = fuentes.titulo.render(f"Fin del dia {dia} de {total}", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(80))))
    izq = pygame.Rect(px(60), px(150), px(400), px(360))
    der = pygame.Rect(px(500), px(150), px(470), px(360))
    for rect, nombre in ((izq, "Asi cambio la ciudad"), (der, "Lo que paso hoy")):
        pygame.draw.rect(pantalla, tema.panel, rect, border_radius=px(12))
        pygame.draw.rect(pantalla, tema.borde, rect, px(2), border_radius=px(12))
        pantalla.blit(fuentes.normal.render(nombre, True, tema.texto), (rect.x + px(16), rect.y + px(12)))
    area = izq.inflate(-px(32), -px(60)).move(0, px(16))
    if any(vars(cambio).values()):
        _dibujar_consecuencias(pantalla, fuentes, tema, area, cambio)
    else:
        pantalla.blit(fuentes.normal.render("Nada cambio hoy.", True, tema.texto), area.topleft)
    y = der.y + px(52)
    for titulo_noticia, accion, delta in decisiones:
        sin = accion in ("sin respuesta", "se acabo el tiempo")
        pantalla.blit(fuentes.normal.render(titulo_noticia, True, tema.texto), (der.x + px(16), y))
        detalle = accion.capitalize() + (f"   credibilidad {delta:+}" if delta else "")
        img = fuentes.chica.render(detalle, True, tema.malo if sin or delta < 0 else tema.acento)
        pantalla.blit(img, (der.x + px(28), y + fuentes.normal.get_linesize()))
        y += fuentes.normal.get_linesize() + fuentes.chica.get_linesize() + px(10)
    color = tema.bueno if cambio_credibilidad > 0 else tema.malo if cambio_credibilidad < 0 else tema.texto
    linea = fuentes.normal.render(f"Tu credibilidad: {credibilidad} ({cambio_credibilidad:+})", True, color)
    pantalla.blit(linea, (izq.x + px(16), izq.bottom - px(40)))
    ayuda = fuentes.normal.render("Enter: seguir", True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(30))))
