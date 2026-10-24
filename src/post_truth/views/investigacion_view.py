"""Ventana de investigacion: pestana Publicacion (la tarjeta en grande y una lupa que revela senales al mantenerla
encima) y pestana Testigos (lista e interrogatorio); a la derecha lo reunido y la conclusion."""
import math
from dataclasses import dataclass

import pygame

from post_truth.config import ANCHO, ALTO, px
from post_truth.models.dominio import NewsEvent
from post_truth.models.pistas import Investigacion, Senal, ZonaTarjeta
from post_truth.models.testigos import Testigo
from post_truth.views.anuncio_view import _icono
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.tarjeta_civitas_view import _layout, dibujar_tarjeta
from post_truth.views.theme import Tema

PESTANAS = ("Publicacion", "Testigos")
RECT_TARJETA = pygame.Rect(px(40), px(104), px(520), px(470))
RECT_REUNIDO = pygame.Rect(px(584), px(104), px(400), px(372))
RECT_LISTA = pygame.Rect(px(40), px(104), px(270), px(470))
RECT_CHARLA = pygame.Rect(px(330), px(104), px(654), px(372))
RADIO_LUPA, ZOOM = px(66), 1.8
VEREDICTOS = (("falsa", "F: Es falsa"), ("verdadera", "V: Es verdadera"), ("no_concluyente", "N: No concluyente"))
TEXTOS_CONCLUSION = {"buena": "Acertaste con buena evidencia.", "a_ciegas": "Acertaste, pero casi a ciegas.",
                     "error": "Te equivocaste: lo reunido no respaldaba eso.",
                     "no_concluyente": "Dejaste la pregunta abierta. A veces es lo prudente."}


def rect_pestana(i: int) -> pygame.Rect:
    return pygame.Rect(px(40) + i * px(180), px(60), px(170), px(34))


def rect_veredicto(i: int) -> pygame.Rect:
    return pygame.Rect(px(584) + i * px(136), px(520), px(128), px(44))


def rect_testigo(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_LISTA.x + px(10), RECT_LISTA.y + px(44) + i * px(62), RECT_LISTA.w - px(20), px(56))


def rect_opcion(i: int) -> pygame.Rect:
    return pygame.Rect(RECT_CHARLA.x + px(14), RECT_CHARLA.bottom - px(14) - (4 - i) * px(40), RECT_CHARLA.w - px(28),
                       px(34))


def zonas_con_senal(evento: NewsEvent) -> dict[ZonaTarjeta, pygame.Rect]:
    zonas = _layout(RECT_TARJETA)
    return {p.zona: zonas[p.zona] for p in evento.clues}


@dataclass
class VistaInvestigacion:
    evento: NewsEvent
    investigacion: Investigacion
    pestana: int
    lupa: tuple[int, int]
    mantenido: float          # 0..1 de lo que falta para revelar la senal bajo la lupa
    testigos: list[tuple[Testigo, bool]]   # (testigo, se puede hablar ya)
    elegido: int
    charla: list[tuple[str, str]]          # (quien, que dijo)
    opciones: list[str]                    # las del nodo actual del interrogatorio
    conclusion: str           # "" o como resulto
    reloj: tuple[float, float] | None
    t: float


def dibujar_investigacion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaInvestigacion) -> None:
    pantalla.fill(tema.fondo)
    titulo = fuentes.grande.render(f"Investigar: {v.evento.title}", True, tema.acento)
    pantalla.blit(titulo, (px(40), px(14)))
    if v.reloj is not None:
        restante, total = v.reloj
        img = fuentes.normal.render(f"Viral: {math.ceil(restante)} s", True,
                                    tema.malo if restante < 0.35 * total else tema.texto)
        pantalla.blit(img, img.get_rect(topright=(ANCHO - px(40), px(20))))
    for i, nombre in enumerate(PESTANAS):
        r = rect_pestana(i)
        activa = i == v.pestana
        pygame.draw.rect(pantalla, tema.boton if activa else tema.panel, r, border_radius=px(8))
        pygame.draw.rect(pantalla, tema.acento if activa else tema.borde, r, px(2), border_radius=px(8))
        img = fuentes.chica.render(nombre, True, tema.boton_texto if activa else tema.texto)
        pantalla.blit(img, img.get_rect(center=r.center))
    if v.pestana == 0:
        _publicacion(pantalla, fuentes, tema, v)
        _reunido(pantalla, fuentes, tema, v)
    else:
        _testigos(pantalla, fuentes, tema, v)
    _conclusion(pantalla, fuentes, tema, v)
    ayuda = ("Mueve la lupa con el raton o las flechas y mantenla sobre algo raro" if v.pestana == 0
             else "Flechas o clic: elegir testigo   Enter: hablar   1-4: preguntar")
    img = fuentes.chica.render(f"{ayuda}   |   Tab: pestana   |   I o ESC: volver", True, tema.texto_off)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, ALTO - px(8))))


def _publicacion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaInvestigacion) -> None:
    capa = pygame.Surface(pantalla.get_size())
    capa.fill(tema.fondo)
    dibujar_tarjeta(capa, fuentes, tema, RECT_TARJETA, v.evento, v.investigacion, ocultas=True)
    pantalla.blit(capa, RECT_TARJETA, RECT_TARJETA)
    # lupa: el pedazo de la tarjeta bajo ella, ampliado y recortado en circulo
    lado = round(2 * RADIO_LUPA / ZOOM)
    origen = pygame.Rect(0, 0, lado, lado)
    origen.center = v.lupa
    origen.clamp_ip(capa.get_rect())
    lente = pygame.Surface((2 * RADIO_LUPA, 2 * RADIO_LUPA), pygame.SRCALPHA)
    lente.blit(pygame.transform.smoothscale(capa.subsurface(origen), lente.get_size()), (0, 0))
    mascara = pygame.Surface(lente.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mascara, (255, 255, 255, 255), (RADIO_LUPA, RADIO_LUPA), RADIO_LUPA)
    lente.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pantalla.blit(lente, lente.get_rect(center=v.lupa))
    pygame.draw.circle(pantalla, tema.texto, v.lupa, RADIO_LUPA, px(4))
    mango = (v.lupa[0] + round(RADIO_LUPA * 0.7), v.lupa[1] + round(RADIO_LUPA * 0.7))
    pygame.draw.line(pantalla, tema.texto, mango, (mango[0] + px(30), mango[1] + px(30)), px(8))
    if v.mantenido > 0:   # cuanto falta para revelar
        caja = pygame.Rect(0, 0, 2 * RADIO_LUPA + px(14), 2 * RADIO_LUPA + px(14))
        caja.center = v.lupa
        pygame.draw.arc(pantalla, tema.acento, caja, math.pi / 2, math.pi / 2 + 2 * math.pi * v.mantenido, px(5))


def _fila_hallazgo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, y: int, senal: Senal | None,
                   titulo: str, texto: str) -> int:
    tipo = {Senal.FALSA: "malo", Senal.VERDADERA: "bueno"}.get(senal, "info")
    _icono(pantalla, tema, tipo, (RECT_REUNIDO.x + px(24), y + px(14)), px(11), 0)
    pantalla.blit(fuentes.chica.render(titulo, True, tema.texto), (RECT_REUNIDO.x + px(44), y))
    linea = ajustar_texto(texto, fuentes.chica, RECT_REUNIDO.w - px(60))[0]
    pantalla.blit(fuentes.chica.render(linea, True, tema.texto_off), (RECT_REUNIDO.x + px(44), y + px(20)))
    return y + px(48)


def _reunido(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaInvestigacion) -> None:
    pygame.draw.rect(pantalla, tema.panel, RECT_REUNIDO, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, RECT_REUNIDO, px(2), border_radius=px(12))
    pantalla.blit(fuentes.normal.render("Lo que encontraste", True, tema.acento), (RECT_REUNIDO.x + px(14), RECT_REUNIDO.y + px(8)))
    y = RECT_REUNIDO.y + px(42)
    inv = v.investigacion
    for h in inv.pistas_descubiertas():
        if y > RECT_REUNIDO.bottom - px(48):
            break
        y = _fila_hallazgo(pantalla, fuentes, tema, y, h.senal, h.titulo, h.hallazgo)
    nombres = {t.id: t.nombre for t, _ in v.testigos}
    for id in inv.testimonios:
        if y > RECT_REUNIDO.bottom - px(48):
            break
        y = _fila_hallazgo(pantalla, fuentes, tema, y, None, f"Testimonio: {nombres.get(id, id)}",
                           "Conto su version (juzga si es fiable).")
    if not inv.descubiertas and not inv.testimonios:
        pantalla.blit(fuentes.chica.render("Nada aun: usa la lupa o habla con los testigos.", True, tema.texto_off),
                      (RECT_REUNIDO.x + px(14), y))


def _testigos(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaInvestigacion) -> None:
    pygame.draw.rect(pantalla, tema.panel, RECT_LISTA, border_radius=px(12))
    pantalla.blit(fuentes.normal.render("Testigos", True, tema.acento), (RECT_LISTA.x + px(14), RECT_LISTA.y + px(8)))
    for i, (t, disponible) in enumerate(v.testigos):
        r = rect_testigo(i)
        elegido = i == v.elegido
        pygame.draw.rect(pantalla, tema.boton if elegido else tema.fondo, r, border_radius=px(8))
        pygame.draw.rect(pantalla, tema.acento if elegido else tema.borde, r, px(2), border_radius=px(8))
        color = tema.boton_texto if elegido else (tema.texto if disponible else tema.texto_off)
        pantalla.blit(fuentes.chica.render(t.nombre, True, color), (r.x + px(10), r.y + px(6)))
        donde = ("Aqui" if t.evidencia is None else f"En {t.lugar.capitalize()}") + ("" if disponible else " (ve alla)")
        if t.id in v.investigacion.testimonios:
            donde += "  - ya hablaron"
        pantalla.blit(fuentes.chica.render(donde, True, color), (r.x + px(10), r.y + px(30)))
    pygame.draw.rect(pantalla, tema.panel, RECT_CHARLA, border_radius=px(12))
    y = RECT_CHARLA.y + px(12)
    limite = rect_opcion(4 - len(v.opciones)).y - px(8) if v.opciones else RECT_CHARLA.bottom - px(12)
    filas = []
    for quien, texto in v.charla:
        lineas = ajustar_texto(f"{quien}: {texto}", fuentes.chica, RECT_CHARLA.w - px(28))
        filas.append((quien == "Tu", lineas))
    alto = sum(len(l) for _, l in filas) * fuentes.chica.get_linesize() + len(filas) * px(6)
    sobra = max(0, alto - (limite - y))   # lo mas nuevo siempre a la vista
    y -= sobra
    for propio, lineas in filas:
        for linea in lineas:
            if y >= RECT_CHARLA.y + px(8):
                pantalla.blit(fuentes.chica.render(linea, True, tema.acento if propio else tema.texto),
                              (RECT_CHARLA.x + px(14), y))
            y += fuentes.chica.get_linesize()
        y += px(6)
    if not v.charla:
        pantalla.blit(fuentes.chica.render("Elige un testigo y pulsa Enter para hablar.", True, tema.texto_off),
                      (RECT_CHARLA.x + px(14), RECT_CHARLA.y + px(12)))
    for i, texto in enumerate(v.opciones):
        r = rect_opcion(4 - len(v.opciones) + i)
        pygame.draw.rect(pantalla, tema.boton, r, border_radius=px(8))
        img = fuentes.chica.render(f"{i + 1}. {texto}", True, tema.boton_texto)
        pantalla.blit(img, img.get_rect(midleft=(r.x + px(10), r.centery)))


def _conclusion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, v: VistaInvestigacion) -> None:
    pantalla.blit(fuentes.normal.render("Tu conclusion", True, tema.acento), (px(584), px(486)))
    if v.conclusion:
        lineas = ajustar_texto(TEXTOS_CONCLUSION[v.conclusion], fuentes.chica, px(400))
        for i, linea in enumerate(lineas):
            pantalla.blit(fuentes.chica.render(linea, True, tema.malo if v.conclusion == "error" else tema.texto),
                          (px(584), px(520) + i * fuentes.chica.get_linesize()))
        return
    for i, (_, texto) in enumerate(VEREDICTOS):
        r = rect_veredicto(i)
        pygame.draw.rect(pantalla, tema.boton, r, border_radius=px(8))
        pygame.draw.rect(pantalla, tema.borde, r, px(2), border_radius=px(8))
        img = fuentes.chica.render(texto, True, tema.boton_texto)
        if img.get_width() > r.w - px(8):
            img = pygame.transform.smoothscale(img, (r.w - px(8), img.get_height() * (r.w - px(8)) // img.get_width()))
        pantalla.blit(img, img.get_rect(center=r.center))
