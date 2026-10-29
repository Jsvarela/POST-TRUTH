"""Vista de la ayuda (F2): indice de secciones a la izquierda y el texto a la derecha, con desplazamiento. La
seccion "Leyenda" dibuja las mismas formas que usa el juego (no dependen del color). Solo dibuja."""
import pygame

from post_truth.config import ANCHO, ALTO, px
from post_truth.models.ayuda import Seccion
from post_truth.views.componentes import Boton, Fuentes, ajustar_texto, panel
from post_truth.views.theme import TOKENS, Tema, esp

RECT_INDICE = pygame.Rect(px(16), px(64), px(230), ALTO - px(108))
RECT_TEXTO = pygame.Rect(px(262), px(64), ANCHO - px(278), ALTO - px(108))
ALTO_ENTRADA = px(28)

# (grupo, [(forma, color del tema, que significa)]): las formas son las del juego en cada pantalla
LEYENDA = [
    ("Telefono: personas de la red", [("circulo_vacio", "texto_off", "no sabe"), ("circulo", "malo", "lo cree"),
                                      ("triangulo", "malo", "lo comparte"), ("cuadrado", "bueno", "inmune")]),
    ("Chat del Colegio", [("circulo", "bueno", "apoyo: atrapalo"), ("triangulo", "malo", "ataque: esquivalo")]),
    ("Mitin de la Plaza", [("cuadrado", "acento", "1 dato"), ("circulo", "detalle", "2 pregunta"),
                           ("triangulo", "bueno", "3 calma")]),
    ("Rueda de prensa", [("triangulo", "acento", "1 pista"), ("cuadrado", "detalle", "2 evidencia"),
                         ("circulo", "bueno", "3 testimonio"), ("x", "malo", "trampa: Espacio")]),
    ("De boca en boca", [("cuadrado_vacio", "texto_off", "no sabe"), ("triangulo", "malo", "lo cree"),
                         ("circulo", "bueno", "convencido"), ("x", "malo", "enojado")]),
    ("En la calle (sobre la cabeza)", [("triangulo", "malo", "lleva un rumor"), ("circulo", "bueno", "testigo"),
                                       ("cuadrado", "detalle", "enojado")]),
]


def rect_entrada(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_INDICE.x + esp(2), RECT_INDICE.y + esp(2) + i * ALTO_ENTRADA, RECT_INDICE.w - 2 * esp(2),
                       ALTO_ENTRADA - px(3))


def area_texto() -> pygame.Rect:
    return RECT_TEXTO.inflate(-2 * esp(4), -2 * esp(4)).move(0, px(22))


def lineas(fuentes: Fuentes, seccion: Seccion) -> list[str]:
    """Las lineas de la seccion ya cortadas al ancho del panel (un renglon en blanco entre parrafos)."""
    salida: list[str] = []
    for parrafo in seccion.lineas:
        salida += ajustar_texto(parrafo, fuentes.normal, area_texto().w) + [""]
    return salida


def visibles(fuentes: Fuentes) -> int:
    return (area_texto().h - px(40)) // fuentes.normal.get_linesize()


def _forma(pantalla: pygame.Surface, forma: str, color, c: tuple[int, int], r: int) -> None:
    x, y = c
    if forma.startswith("circulo"):
        pygame.draw.circle(pantalla, color, c, r, px(3) if forma.endswith("vacio") else 0)
    elif forma.startswith("cuadrado"):
        pygame.draw.rect(pantalla, color, (x - r, y - r, 2 * r, 2 * r), px(3) if forma.endswith("vacio") else 0,
                         border_radius=px(3))
    elif forma == "triangulo":
        pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    else:
        pygame.draw.line(pantalla, color, (x - r, y - r), (x + r, y + r), px(4))
        pygame.draw.line(pantalla, color, (x - r, y + r), (x + r, y - r), px(4))


def _leyenda(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, area: pygame.Rect) -> None:
    y = area.y
    for grupo, formas in LEYENDA:
        pantalla.blit(fuentes.normal.render(grupo, True, tema.acento), (area.x, y))
        y += fuentes.normal.get_linesize()
        ancho = area.w // 4
        for i, (forma, color, texto) in enumerate(formas):
            x = area.x + i * ancho
            _forma(pantalla, forma, getattr(tema, color), (x + px(12), y + px(11)), px(9))
            pantalla.blit(fuentes.chica.render(texto, True, tema.texto), (x + px(28), y + px(2)))
        y += px(30)


def dibujar_ayuda(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, secciones: tuple[Seccion, ...],
                  actual: int, desde: int) -> None:
    velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
    velo.fill((*tema.fondo, TOKENS.alfa_velo))
    pantalla.blit(velo, (0, 0))
    pygame.draw.rect(pantalla, tema.fondo, (0, 0, ANCHO, RECT_INDICE.y - esp(1)))   # tapa el titulo de abajo
    titulo = fuentes.titulo.render("Ayuda", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(14))))
    panel(pantalla, tema, RECT_INDICE, 255)
    for i, s in enumerate(secciones):
        b = Boton(rect_entrada(i), s.titulo, lambda: None)
        b.foco = i == actual
        b.draw(pantalla, fuentes.chica, tema)
    panel(pantalla, tema, RECT_TEXTO, 255, borde=tema.acento)
    s = secciones[actual]
    pantalla.blit(fuentes.grande.render(s.titulo, True, tema.acento), (RECT_TEXTO.x + esp(4), RECT_TEXTO.y + esp(3)))
    area = area_texto().move(0, px(16))
    if s.id == "leyenda":
        _leyenda(pantalla, fuentes, tema, area)
    else:
        todas = lineas(fuentes, s)
        n = visibles(fuentes)
        y = area.y
        for linea in todas[desde:desde + n]:
            pantalla.blit(fuentes.normal.render(linea, True, tema.texto), (area.x, y))
            y += fuentes.normal.get_linesize()
        if len(todas) > n:   # se puede desplazar: indicador abajo
            img = fuentes.chica.render(f"Lineas {desde + 1}-{min(len(todas), desde + n)} de {len(todas)}  "
                                       "(PgUp/PgDn o la rueda)", True, tema.texto_off)
            pantalla.blit(img, img.get_rect(bottomright=(RECT_TEXTO.right - esp(3), RECT_TEXTO.bottom - esp(2))))
    pygame.draw.rect(pantalla, tema.fondo, (0, RECT_INDICE.bottom + esp(1), ANCHO, ALTO - RECT_INDICE.bottom))   # tapa el pie de abajo
    pie = fuentes.chica.render("Flechas o clic: seccion   |   PgUp/PgDn o rueda: desplazar   |   F2 o ESC: cerrar",
                               True, tema.texto)
    pantalla.blit(pie, pie.get_rect(midbottom=(ANCHO // 2, ALTO - esp(2))))
