"""Vista de la escena de dialogo: HUD compacto, personaje, panel de noticia/consecuencias,
caja de dialogo y botones. Solo dibuja datos que le entrega el controlador."""
from dataclasses import fields

import pygame

from post_truth.models import Impact
from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Boton, CajaDialogo, Fuentes, Panel, dibujar_texto_ajustado
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, dibujar_mapa
from post_truth.views.personaje_view import dibujar_personaje
from post_truth.views.theme import Tema
from post_truth.views.zona_view import dibujar_fondo_zona

# Nombre corto de cada indicador en el HUD (las barras son pequenas a proposito:
# los indicadores acompanan la historia, no son el protagonista).
HUD_NOMBRES = {
    "Informacion verificada": "Info verificada", "Confianza ciudadana": "Confianza",
    "Convivencia": "Convivencia", "Bienestar digital": "Bienestar",
    "Desinformacion": "Desinformacion", "Conflictos": "Conflictos",
}
# Indicadores donde subir es malo (se pintan con el color de peligro del tema).
NEGATIVOS = {"Desinformacion", "Conflictos"}

# Campos de Impact -> (etiqueta, subir es malo?)
ETIQUETAS_IMPACTO = {
    "verified_information": ("Info verificada", False), "trust": ("Confianza", False),
    "coexistence": ("Convivencia", False), "digital_wellbeing": ("Bienestar", False),
    "misinformation": ("Desinformacion", True), "conflicts": ("Conflictos", True),
    "score": ("Puntaje", False),
}

RECT_HUD = pygame.Rect(0, 0, 1024, 56)
RECT_PERSONAJE = pygame.Rect(40, 64, 260, 336)
RECT_PANEL = pygame.Rect(330, 68, 664, 328)
RECT_ESCENA = pygame.Rect(0, 57, 1024, 347)      # area del fondo de la zona (entre el HUD y el dialogo)
RECT_MAPA = pygame.Rect(RECT_PANEL.right - 290, RECT_PANEL.y + 46, 272, 272)  # minimapa dentro del panel
RECT_TEXTO_PANEL = pygame.Rect(RECT_PANEL.x + 18, RECT_PANEL.y + 52, 340, 256)  # texto a la izquierda del mapa
ALFA_PANEL = 205  # el panel deja ver un poco el fondo de la zona


def _dibujar_hud(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema,
                 filas: list[tuple[str, int]]) -> None:
    pygame.draw.rect(pantalla, tema.panel, RECT_HUD)
    pygame.draw.line(pantalla, tema.borde, RECT_HUD.bottomleft, RECT_HUD.bottomright, 2)
    x = 14
    for nombre, valor in filas:
        if nombre.startswith("Puntaje"):  # no es un indicador 0-100: va como texto
            img = fuentes.normal.render(f"Puntaje {valor}", True, tema.texto)
            pantalla.blit(img, img.get_rect(midright=(RECT_HUD.right - 16, RECT_HUD.centery)))
            continue
        pantalla.blit(fuentes.chica.render(f"{HUD_NOMBRES.get(nombre, nombre)} {valor}", True, tema.texto), (x, 7))
        pygame.draw.rect(pantalla, tema.fondo, (x, 32, 126, 10), border_radius=4)
        color = tema.malo if nombre in NEGATIVOS else tema.bueno
        pygame.draw.rect(pantalla, color, (x, 32, round(1.26 * valor), 10), border_radius=4)
        x += 138


def _dibujar_consecuencias(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema,
                           area: pygame.Rect, impacto: Impact) -> None:
    y = area.y
    for campo in fields(impacto):
        valor = getattr(impacto, campo.name)
        if valor == 0:
            continue
        etiqueta, sube_es_malo = ETIQUETAS_IMPACTO[campo.name]
        bueno = (valor > 0) != sube_es_malo
        color = tema.bueno if bueno else tema.malo
        # Triangulo ademas del color: la informacion no depende solo del tono (daltonismo).
        # Se dibuja con poligono, no con un glifo, porque no toda fuente trae flechas.
        cy = y + fuentes.normal.get_linesize() // 2
        if valor > 0:
            puntos = [(area.x, cy + 6), (area.x + 14, cy + 6), (area.x + 7, cy - 6)]
        else:
            puntos = [(area.x, cy - 6), (area.x + 14, cy - 6), (area.x + 7, cy + 6)]
        pygame.draw.polygon(pantalla, color, puntos)
        pantalla.blit(fuentes.normal.render(f"{etiqueta} {valor:+}", True, color), (area.x + 24, y))
        y += fuentes.normal.get_linesize() + 6


def dibujar_escena(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, personaje: Personaje,
                   animo: int, filas: list[tuple[str, int]], titulo_panel: str, texto_panel: str,
                   impacto: Impact | None, dialogo: CajaDialogo, botones: list[Boton],
                   animacion: AnimacionPropagacion | None = None, zona_id: str = "", nombre_zona: str = "",
                   mapa: EstadoMapa | None = None) -> None:
    pantalla.fill(tema.fondo)
    dibujar_fondo_zona(pantalla, zona_id, tema, RECT_ESCENA)  # el escenario cambia con la zona
    _dibujar_hud(pantalla, fuentes, tema, filas)
    dibujar_personaje(pantalla, personaje, tema, RECT_PERSONAJE, animo)
    if nombre_zona:
        etiqueta = fuentes.normal.render(f"Estas en: {nombre_zona}", True, tema.texto)
        marco = etiqueta.get_rect(topleft=(16, RECT_ESCENA.y + 12)).inflate(20, 10)
        pygame.draw.rect(pantalla, tema.panel, marco, border_radius=8)
        pygame.draw.rect(pantalla, tema.acento, marco, width=2, border_radius=8)
        pantalla.blit(etiqueta, etiqueta.get_rect(center=marco.center))
    if animacion is not None:  # la propagacion ocupa el lugar del panel de noticia
        animacion.draw(pantalla, fuentes, tema, RECT_PANEL)
    else:
        panel = Panel(RECT_PANEL, titulo_panel, alfa=ALFA_PANEL)
        panel.draw(pantalla, fuentes, tema)
        area = RECT_TEXTO_PANEL if mapa is not None else panel.interior
        if impacto is None:
            dibujar_texto_ajustado(pantalla, fuentes.normal, texto_panel, tema.texto, area)
        else:
            _dibujar_consecuencias(pantalla, fuentes, tema, area, impacto)
        if mapa is not None:
            dibujar_mapa(pantalla, fuentes, tema, RECT_MAPA, mapa)
    dialogo.draw(pantalla, fuentes, tema)
    for boton in botones:
        boton.draw(pantalla, fuentes.normal, tema)
