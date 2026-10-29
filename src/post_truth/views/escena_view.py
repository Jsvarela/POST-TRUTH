"""Vista de la escena de dialogo."""
import math
from dataclasses import dataclass, fields

import pygame

from post_truth.config import ANCHO, px
from post_truth.models import Impact
from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Boton, CajaDialogo, Fuentes, Panel, dibujar_texto_ajustado
from post_truth.views.grafo_view import AnimacionPropagacion
from post_truth.views.mapa_view import EstadoMapa, dibujar_mapa
from post_truth.views.tarjeta_civitas_view import EstadoTarjeta, dibujar_tarjeta
from post_truth.views.personaje_view import dibujar_personaje, dibujar_personaje_mundo
from post_truth.views.theme import Tema
from post_truth.views.zona_view import dibujar_fondo_zona

ETIQUETAS_IMPACTO = {
    "verified_information": ("Info verificada", False), "trust": ("Confianza", False),
    "coexistence": ("Convivencia", False), "digital_wellbeing": ("Bienestar", False),
    "misinformation": ("Desinformacion", True), "conflicts": ("Conflictos", True),
    "score": ("Puntaje", False),
}

RECT_HUD = pygame.Rect(0, 0, ANCHO, px(56))   # franja del HUD en fila (lo dibuja la capa global)
RECT_PERSONAJE = pygame.Rect(px(40), px(138), px(260), px(262))   # el pixel art llena el alto: deja libre el reloj viral
RECT_PANEL = pygame.Rect(px(330), px(68), px(664), px(328))
RECT_ESCENA = pygame.Rect(0, px(57), ANCHO, px(404) - px(57))
RECT_TARJETA = pygame.Rect(RECT_PANEL.x + px(12), RECT_PANEL.y + px(8), px(346), px(312))
RECT_MAPA = pygame.Rect(RECT_PANEL.right - px(10) - px(290), RECT_PANEL.y + px(8), px(290), px(312))
AYUDA_INTERIOR = "Investigar: I (lupa y testigos)   |   Decidir: 1-4   |   ESC: volver a la calle"
AYUDA = "Investigar: clic en la publicacion o A S D F G   |   Viajar: clic en el mapa o Q W E R T   |   Decidir: 1-4"
RECT_TEXTO_PANEL = pygame.Rect(RECT_PANEL.x + px(18), RECT_PANEL.y + px(52), px(340), px(256))
ALFA_PANEL = 205


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
        cy = y + fuentes.normal.get_linesize() // 2
        a, b, m = px(6), px(14), px(7)
        if valor > 0:
            puntos = [(area.x, cy + a), (area.x + b, cy + a), (area.x + m, cy - a)]
        else:
            puntos = [(area.x, cy - a), (area.x + b, cy - a), (area.x + m, cy + a)]
        pygame.draw.polygon(pantalla, color, puntos)
        pantalla.blit(fuentes.normal.render(f"{etiqueta} {valor:+}", True, color), (area.x + px(24), y))
        y += fuentes.normal.get_linesize() + px(6)


DURACION_REACCION = 0.8   # segundos que dura el salto o la sacudida tras decidir


@dataclass
class EstadoPresentes:
    """Ciudadanos en el lugar: (nombre, apariencia, si le llego la publicacion). `reaccion` es None mientras se
    decide; despues, el signo del impacto (1 bien, -1 mal, 0 nada)."""
    personas: list[tuple[str, Personaje, bool]]
    reaccion: int | None = None
    t: float = 0.0             # reloj de la escena (respiracion)
    t_reaccion: float = 0.0    # segundos desde que se decidio


def desplazamiento_reaccion(signo: int, t: float) -> tuple[int, int]:
    """Bien: dos saltos cortos. Mal: una sacudida que se apaga. Despues de DURACION_REACCION, quieto."""
    if t >= DURACION_REACCION or signo == 0:
        return 0, 0
    if signo > 0:
        return 0, -round(abs(math.sin(t * 2 * math.pi / DURACION_REACCION)) * px(14))
    return round(math.sin(t * 40) * px(6) * (1 - t / DURACION_REACCION)), 0


def dibujar_presentes(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                      estado: EstadoPresentes) -> None:
    pygame.draw.rect(pantalla, tema.fondo, rect)
    pygame.draw.rect(pantalla, tema.borde, rect, width=px(2))
    titulo = fuentes.normal.render("En el lugar", True, tema.texto)
    pantalla.blit(titulo, (rect.x + px(14), rect.y + px(10)))
    n = len(estado.personas)
    for i, (nombre, apariencia, le_llego) in enumerate(estado.personas):
        x = rect.x + round(rect.w * (i + 0.5) / n)
        pies = (x, rect.bottom - px(46))
        signo = estado.reaccion or 0
        dx, dy = desplazamiento_reaccion(signo, max(0.0, estado.t_reaccion - i * 0.1))   # no todos a la vez
        cuadro = int((estado.t + i * 0.3) * 2) % 2
        dibujar_personaje_mundo(pantalla, apariencia, tema, (pies[0] + dx, pies[1] + dy), px(120), "idle_abajo", cuadro)
        img = fuentes.chica.render(nombre.split()[0], True, tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(x, pies[1] + px(6))))
        if estado.reaccion is not None:
            _globo_reaccion(pantalla, fuentes, tema, (x + dx, pies[1] - px(132) + dy), signo)
            if le_llego:   # la publicacion le llego por Civitas: un celular junto a la persona
                tel = pygame.Rect(0, 0, px(12), px(20))
                tel.midleft = (x + px(26), pies[1] - px(70))
                pygame.draw.rect(pantalla, tema.texto, tel)
                pygame.draw.rect(pantalla, tema.acento, tel.inflate(-px(4), -px(6)))


def _globo_reaccion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, centro: tuple[int, int], signo: int) -> None:
    """Visto (bien), alerta (mal) o puntos suspensivos (nada): forma distinta en cada caso, no solo color."""
    x, y = centro
    r = px(12)
    if signo > 0:
        pygame.draw.circle(pantalla, tema.bueno, centro, r)
        pygame.draw.lines(pantalla, tema.fondo, False, [(x - px(6), y), (x - px(2), y + px(5)), (x + px(6), y - px(5))], px(3))
    elif signo < 0:
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - r), (x + r, y + r - px(2)), (x - r, y + r - px(2))])
        img = fuentes.chica.render("!", True, tema.fondo)
        pantalla.blit(img, img.get_rect(center=(x, y + px(2))))
    else:
        caja = pygame.Rect(0, 0, px(28), px(18))
        caja.center = centro
        pygame.draw.rect(pantalla, tema.panel, caja)
        pygame.draw.rect(pantalla, tema.borde, caja, width=px(1))
        for k in (-1, 0, 1):
            pygame.draw.circle(pantalla, tema.texto, (x + k * px(7), y), px(2))


AVISO_RELOJ = 10   # segundos: desde aqui el reloj usa el color de peligro
PULSO_RELOJ = 5    # segundos: desde aqui ademas late


def dibujar_reloj(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, restante: float, total: float,
                  topleft: tuple[int, int]) -> None:
    """Reloj de una publicacion viral: icono, segundos y barra que se vacia. Al final cambia de color, de texto
    ("Rapido!") y late, asi que no depende solo del color."""
    urgente = restante <= AVISO_RELOJ
    color = tema.malo if urgente else tema.acento
    caja = pygame.Rect(*topleft, px(200), px(32))   # cabe sobre la cabeza del personaje
    if restante <= PULSO_RELOJ and int(restante * 4) % 2 == 0:
        caja = caja.inflate(px(6), px(2))
    pygame.draw.rect(pantalla, tema.panel, caja)
    pygame.draw.rect(pantalla, color, caja, px(3) if urgente else px(2))
    centro, r = (caja.x + px(17), caja.y + px(14)), px(8)           # reloj: circulo con dos agujas
    pygame.draw.circle(pantalla, color, centro, r, px(2))
    ang = -math.pi / 2 + 2 * math.pi * (1 - restante / total)
    pygame.draw.line(pantalla, color, centro, (centro[0] + round(math.cos(ang) * r * 0.8),
                                               centro[1] + round(math.sin(ang) * r * 0.8)), px(2))
    pygame.draw.line(pantalla, color, centro, (centro[0], centro[1] - r // 2), px(2))
    texto = f"Viral: {math.ceil(restante)} s" + ("  Rapido!" if urgente else "")
    img = fuentes.normal.render(texto, True, tema.texto)
    pantalla.blit(img, img.get_rect(midleft=(caja.x + px(32), centro[1])))
    barra = pygame.Rect(caja.x + px(8), caja.bottom - px(6), caja.w - px(16), px(3))
    pygame.draw.rect(pantalla, tema.fondo, barra)
    lleno = barra.copy()
    lleno.w = round(barra.w * max(0.0, min(1.0, restante / total)))
    if lleno.w:
        pygame.draw.rect(pantalla, color, lleno)


def dibujar_escena(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, personaje: Personaje,
                   animo: int, filas: list[tuple[str, int]], titulo_panel: str, texto_panel: str,
                   impacto: Impact | None, dialogo: CajaDialogo, botones: list[Boton],
                   animacion: AnimacionPropagacion | None = None, zona_id: str = "", nombre_zona: str = "",
                   mapa: EstadoMapa | None = None, tarjeta: EstadoTarjeta | None = None, ayuda: str = AYUDA,
                   reloj: tuple[float, float] | None = None, presentes: EstadoPresentes | None = None,
                   reaccion_jugador: tuple[int, float] | None = None, credibilidad: int | None = None) -> None:
    pantalla.fill(tema.fondo)
    dibujar_fondo_zona(pantalla, zona_id, tema, RECT_ESCENA)
    dx, dy = desplazamiento_reaccion(*reaccion_jugador) if reaccion_jugador else (0, 0)
    dibujar_personaje(pantalla, personaje, tema, RECT_PERSONAJE.move(dx, dy), animo)
    if nombre_zona:
        etiqueta = fuentes.normal.render(f"Estas en: {nombre_zona}", True, tema.texto)
        marco = etiqueta.get_rect(topleft=(px(16), RECT_ESCENA.y + px(12))).inflate(px(20), px(10))
        pygame.draw.rect(pantalla, tema.panel, marco)
        pygame.draw.rect(pantalla, tema.acento, marco, width=px(2))
        pantalla.blit(etiqueta, etiqueta.get_rect(center=marco.center))
    if reloj is not None:
        dibujar_reloj(pantalla, fuentes, tema, *reloj, (px(16), RECT_ESCENA.y + px(56)))
    if animacion is not None:
        animacion.draw(pantalla, fuentes, tema, RECT_PANEL)
    else:
        panel = Panel(RECT_PANEL, "" if tarjeta is not None else titulo_panel, alfa=ALFA_PANEL)
        panel.draw(pantalla, fuentes, tema)
        area = RECT_TEXTO_PANEL if mapa is not None or presentes is not None else panel.interior
        if tarjeta is not None:
            dibujar_tarjeta(pantalla, fuentes, tema, RECT_TARJETA, tarjeta.evento, tarjeta.investigacion, tarjeta.hover,
                            tarjeta.ocultas)
        elif impacto is None:
            dibujar_texto_ajustado(pantalla, fuentes.normal, texto_panel, tema.texto, area)
        else:
            _dibujar_consecuencias(pantalla, fuentes, tema, area, impacto)
        if presentes is not None:
            dibujar_presentes(pantalla, fuentes, tema, RECT_MAPA, presentes)
        elif mapa is not None:
            dibujar_mapa(pantalla, fuentes, tema, RECT_MAPA, mapa)
    dialogo.draw(pantalla, fuentes, tema)
    for boton in botones:
        boton.draw(pantalla, fuentes.normal, tema)
    if tarjeta is not None:
        ayuda = fuentes.chica.render(ayuda, True, tema.texto)
        pantalla.blit(ayuda, ayuda.get_rect(midbottom=(pantalla.get_width() // 2, pantalla.get_height() - px(6))))
