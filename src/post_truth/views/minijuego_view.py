"""Vista de los minijuegos: marco comun (titulo, tiempo, pausa y resultado) y el dibujo propio de cada uno."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.minijuego import Ensayo, Minijuego, ResultadoMinijuego
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import _dibujar_consecuencias, _dibujar_hud
from post_truth.views.theme import Tema


def dibujar_minijuego(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Minijuego,
                      filas: list[tuple[str, int]], credibilidad: int, resultado: ResultadoMinijuego | None,
                      pausado: bool) -> None:
    pantalla.fill(tema.fondo)
    _dibujar_hud(pantalla, fuentes, tema, filas, credibilidad)
    titulo = fuentes.titulo.render(f"{m.nombre} en {m.contexto.lugar.capitalize()}", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(72))))
    if resultado is not None:
        _dibujar_resultado(pantalla, fuentes, tema, resultado)
    else:
        DIBUJOS[m.id](pantalla, fuentes, tema, m)
        if pausado:
            velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
            velo.fill((*tema.fondo, 200))
            pantalla.blit(velo, (0, 0))
            img = fuentes.titulo.render("Pausa (P para seguir)", True, tema.texto)
            pantalla.blit(img, img.get_rect(center=pantalla.get_rect().center))
    ayuda = "Enter: volver a la calle" if resultado else "1-2: responder   |   P: pausa"
    img = fuentes.chica.render(ayuda, True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(10))))


def _dibujar_resultado(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, r: ResultadoMinijuego) -> None:
    caja = pygame.Rect(px(212), px(140), px(600), px(380))
    pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(12))
    pantalla.blit(fuentes.normal.render(r.texto, True, tema.texto), (caja.x + px(20), caja.y + px(16)))
    _dibujar_consecuencias(pantalla, fuentes, tema, pygame.Rect(caja.x + px(20), caja.y + px(60), caja.w, caja.h), r.impacto)
    color = tema.bueno if r.credibilidad > 0 else tema.malo if r.credibilidad < 0 else tema.texto
    img = fuentes.normal.render(f"Credibilidad {r.credibilidad:+}", True, color)
    pantalla.blit(img, (caja.x + px(20), caja.bottom - px(44)))


def _dibujar_ensayo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Ensayo) -> None:
    actual = m.mensaje_actual
    if actual is None:
        return
    texto, (calma, impulso) = actual
    globo = pygame.Rect(px(140), px(150), px(744), px(120))
    pygame.draw.rect(pantalla, tema.panel, globo, border_radius=px(16))
    pygame.draw.rect(pantalla, tema.borde, globo, px(2), border_radius=px(16))
    y = globo.y + px(16)
    for linea in ajustar_texto(texto, fuentes.normal, globo.w - px(40)):
        pantalla.blit(fuentes.normal.render(linea, True, tema.texto), (globo.x + px(20), y))
        y += fuentes.normal.get_linesize()
    for i, opcion in enumerate((calma, impulso)):
        boton = pygame.Rect(px(140) + i * px(384), px(310), px(360), px(80))
        pygame.draw.rect(pantalla, tema.boton, boton, border_radius=px(12))
        pygame.draw.rect(pantalla, tema.borde, boton, px(2), border_radius=px(12))
        img = fuentes.normal.render(f"{i + 1}. {opcion}", True, tema.boton_texto)
        pantalla.blit(img, img.get_rect(center=boton.center))
    barra = pygame.Rect(px(140), px(420), px(744), px(10))
    pygame.draw.rect(pantalla, tema.panel, barra, border_radius=px(5))
    resto = max(0.0, 1 - m.t / m.limite)
    color = tema.malo if resto < 0.35 else tema.acento
    pygame.draw.rect(pantalla, color, (barra.x, barra.y, round(barra.w * resto), barra.h), border_radius=px(5))
    progreso = fuentes.chica.render(f"Mensaje {len(m.respuestas) + 1} de {len(m.mensajes)}", True, tema.texto)
    pantalla.blit(progreso, (barra.x, barra.bottom + px(8)))


DIBUJOS = {"ensayo": _dibujar_ensayo}   # cada minijuego nuevo agrega aqui su dibujo
