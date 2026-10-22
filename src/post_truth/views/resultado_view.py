"""Vista de la eleccion del alcalde: votos por candidato, ganador, por que gano y la evaluacion del jugador."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.eleccion import ResultadoEleccion
from post_truth.models.intro import Candidato
from post_truth.views.componentes import Fuentes
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import Tema


def explicacion(r: ResultadoEleccion, nombres: dict[str, str]) -> str:
    ganador = nombres[r.ganador]
    if r.hundido_por_rumor:
        return f"Gano {ganador}, pero sin los rumores falsos habria ganado {nombres[r.hundido_por_rumor]}."
    return f"Gano {ganador} con sus propuestas: los rumores no decidieron la eleccion."


def dibujar_resultado(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, r: ResultadoEleccion,
                      candidatos: list[Candidato], puntos: int, progreso: float) -> None:
    """`progreso` (0..1) hace crecer las barras al entrar."""
    pantalla.fill(tema.fondo)
    titulo = fuentes.titulo.render("Eleccion del alcalde", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(24))))
    nombres = {c.id: c.nombre for c in candidatos}
    ancho_col = px(220)
    x0 = (ANCHO - ancho_col * len(candidatos)) // 2
    base = px(400)
    for i, c in enumerate(candidatos):
        x = x0 + i * ancho_col + ancho_col // 2
        gano = c.id == r.ganador
        retrato = pygame.Rect(x - px(55), px(100), px(110), px(130))
        dibujar_retrato(pantalla, c.aspecto, tema, retrato)
        alto = round(px(160) * r.votos[c.id] / max(r.votos.values()) * progreso)   # la mas alta llena la columna
        barra = pygame.Rect(x - px(30), base - alto, px(60), alto)
        pygame.draw.rect(pantalla, tema.acento if gano else tema.borde, barra, border_radius=px(4))
        if gano and progreso >= 1:   # ademas del color, una corona: no depende solo del color
            y = retrato.top - px(2)
            pygame.draw.polygon(pantalla, tema.detalle, [(x - px(18), y), (x - px(18), y - px(16)), (x - px(9), y - px(8)),
                                                          (x, y - px(20)), (x + px(9), y - px(8)), (x + px(18), y - px(16)),
                                                          (x + px(18), y)])
        for texto, y, color in ((c.nombre, base + px(8), tema.texto),
                                (f"{r.votos[c.id] * progreso:.0f}%", base + px(32), tema.acento if gano else tema.texto)):
            img = fuentes.normal.render(texto, True, color)
            pantalla.blit(img, img.get_rect(midtop=(x, y)))
    lineas = [(explicacion(r, nombres), tema.texto),
              (f"Participacion: {r.participacion}% de la ciudad voto.", tema.texto),
              (f"Tu resultado: {r.titulo_jugador}  |  Puntaje {puntos}", tema.acento)]
    y = px(480)
    for texto, color in lineas:
        img = fuentes.normal.render(texto, True, color)
        pantalla.blit(img, img.get_rect(midtop=(ANCHO // 2, y)))
        y += fuentes.normal.get_linesize() + px(8)
    ayuda = fuentes.chica.render("Enter: volver al menu", True, tema.texto)
    pantalla.blit(ayuda, ayuda.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(14))))
