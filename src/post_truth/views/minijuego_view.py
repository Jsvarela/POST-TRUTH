"""Vista de los minijuegos: marco comun (titulo, tiempo, pausa y resultado) y el dibujo propio de cada uno."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.chat import Chat
from post_truth.models.minijuego import Ensayo, Minijuego, ResultadoMinijuego
from post_truth.models.mitin import ACIERTO, DESTIEMPO, FALLO, Mitin
from post_truth.models.mitin import datos as datos_mitin
from post_truth.views.componentes import Fuentes, ajustar_texto
from post_truth.views.escena_view import _dibujar_consecuencias
from post_truth.views.theme import Tema


def dibujar_minijuego(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Minijuego,
                      filas: list[tuple[str, int]], credibilidad: int, resultado: ResultadoMinijuego | None,
                      pausado: bool) -> None:
    pantalla.fill(tema.fondo)
    titulo = fuentes.titulo.render(f"{m.nombre} en {m.contexto.lugar.capitalize()}", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(72))))
    if resultado is not None:
        _dibujar_resultado(pantalla, fuentes, tema, resultado)
    else:
        y = px(122)
        for linea in ajustar_texto(m.ayuda, fuentes.chica, px(820)):   # ayuda siempre a la vista
            img = fuentes.chica.render(linea, True, tema.texto_off)
            pantalla.blit(img, img.get_rect(midtop=(ANCHO // 2, y)))
            y += fuentes.chica.get_linesize()
        DIBUJOS[m.id](pantalla, fuentes, tema, m)
        if pausado:
            velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
            velo.fill((*tema.fondo, 200))
            pantalla.blit(velo, (0, 0))
            img = fuentes.titulo.render("Pausa (P para seguir)", True, tema.texto)
            pantalla.blit(img, img.get_rect(center=pantalla.get_rect().center))
    teclas = "1-2" if m.id == "ensayo" else "1-3"
    ayuda = "Enter: volver a la calle" if resultado else f"{teclas}: responder   |   P: pausa"
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
    globo = pygame.Rect(px(140), px(170), px(744), px(100))
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


def _barra_tiempo(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect, resto: float) -> None:
    pygame.draw.rect(pantalla, tema.panel, rect, border_radius=rect.h // 2)
    color = tema.malo if resto < 0.35 else tema.acento
    pygame.draw.rect(pantalla, color, (rect.x, rect.y, round(rect.w * resto), rect.h), border_radius=rect.h // 2)


def _globo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, x: int, y: int, ancho: int, quien: str,
           texto: str, propio: bool) -> int:
    """Un mensaje del chat; los del jugador a la derecha. Devuelve la y de abajo."""
    lineas = ajustar_texto(texto, fuentes.chica, ancho - px(24))
    alto = px(30) + len(lineas) * fuentes.chica.get_linesize()
    caja = pygame.Rect(x + (px(744) - ancho if propio else 0), y, ancho, alto)
    pygame.draw.rect(pantalla, tema.boton if propio else tema.panel, caja, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, caja, px(2), border_radius=px(12))
    color = tema.boton_texto if propio else tema.acento
    pantalla.blit(fuentes.chica.render("Tu" if propio else quien, True, color), (caja.x + px(12), caja.y + px(4)))
    for i, linea in enumerate(lineas):
        pantalla.blit(fuentes.chica.render(linea, True, tema.boton_texto if propio else tema.texto),
                      (caja.x + px(12), caja.y + px(24) + i * fuentes.chica.get_linesize()))
    return caja.bottom


def _dibujar_chat(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Chat) -> None:
    nodo = m.nodo_actual
    if nodo is None:
        return
    x, y = px(140), px(172)
    for quien, mensaje, respuesta in m.historia[-1:]:   # el turno anterior, para no perder el hilo
        y = _globo(pantalla, fuentes, tema, x, y, px(520), quien, mensaje, False) + px(6)
        y = _globo(pantalla, fuentes, tema, x, y, px(520), "", respuesta, True) + px(6)
    _globo(pantalla, fuentes, tema, x, y, px(600), nodo.hablante, nodo.texto, False)
    for i, opcion in enumerate(nodo.opciones):
        boton = pygame.Rect(px(140), px(430) + i * px(46), px(744), px(40))
        pygame.draw.rect(pantalla, tema.boton, boton, border_radius=px(10))
        pygame.draw.rect(pantalla, tema.borde, boton, px(2), border_radius=px(10))
        img = fuentes.chica.render(f"{i + 1}. {opcion.texto}", True, tema.boton_texto)
        pantalla.blit(img, img.get_rect(midleft=(boton.x + px(14), boton.centery)))
    _barra_tiempo(pantalla, tema, pygame.Rect(px(140), px(572), px(744), px(10)), max(0.0, 1 - m.t / m.limite))


SIMBOLOS = {ACIERTO: "Bien", DESTIEMPO: "A destiempo", FALLO: "Fallo", "sin_pruebas": "Sin pruebas"}


def _dibujar_mitin(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Mitin) -> None:
    r = m.actual
    if r is None:
        return
    # la multitud: personas animadas (circulo arriba) o molestas (cuadrado) segun el animo
    animadas = round(24 * m.animo / 100)
    for k in range(24):
        cx, cy = px(150) + (k % 12) * px(62), px(184) + (k // 12) * px(34)
        if k < animadas:
            pygame.draw.circle(pantalla, tema.bueno, (cx, cy), px(11))
        else:
            pygame.draw.rect(pantalla, tema.malo, (cx - px(10), cy - px(10), px(20), px(20)), border_radius=px(3))
    barra = pygame.Rect(px(140), px(232), px(744), px(12))
    pygame.draw.rect(pantalla, tema.panel, barra, border_radius=px(6))
    pygame.draw.rect(pantalla, tema.bueno, (barra.x, barra.y, round(barra.w * m.animo / 100), barra.h),
                     border_radius=px(6))
    pantalla.blit(fuentes.chica.render(f"Animo de la multitud {round(m.animo)}", True, tema.texto),
                  (barra.x, barra.bottom + px(2)))
    globo = pygame.Rect(px(140), px(272), px(744), px(46))
    pygame.draw.rect(pantalla, tema.panel, globo, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.malo, globo, px(2), border_radius=px(12))
    img = fuentes.normal.render(f"Alguien grita: {r['grito']}", True, tema.texto)
    pantalla.blit(img, img.get_rect(midleft=(globo.x + px(14), globo.centery)))
    ritmo = pygame.Rect(px(140), px(330), px(744), px(26))
    pygame.draw.rect(pantalla, tema.panel, ritmo, border_radius=px(8))
    a, b = (0.0, 1.0) if m.sin_ritmo else datos_mitin()["ventana"]
    zona = pygame.Rect(ritmo.x + round(ritmo.w * a), ritmo.y, round(ritmo.w * (b - a)), ritmo.h)
    pygame.draw.rect(pantalla, tema.acento if m.en_ventana else tema.borde, zona, border_radius=px(8))
    xm = ritmo.x + round(ritmo.w * m.marcador)
    pygame.draw.line(pantalla, tema.texto, (xm, ritmo.y - px(6)), (xm, ritmo.bottom + px(6)), px(4))
    nota = "Sin ritmo (tiempo extendido): responde cuando quieras" if m.sin_ritmo else "Responde cuando la linea este en la zona clara"
    pantalla.blit(fuentes.chica.render(nota, True, tema.texto_off), (ritmo.x, ritmo.bottom + px(4)))
    for i, argumento in enumerate(r["argumentos"]):
        boton = pygame.Rect(px(140), px(384) + i * px(46), px(744), px(40))
        pygame.draw.rect(pantalla, tema.boton, boton, border_radius=px(10))
        pygame.draw.rect(pantalla, tema.borde, boton, px(2), border_radius=px(10))
        img = fuentes.chica.render(f"{i + 1}. {argumento}", True, tema.boton_texto)
        pantalla.blit(img, img.get_rect(midleft=(boton.x + px(14), boton.centery)))
    x = px(140)
    texto = f"Evidencia reunida: {m.contexto.evidencias}   |   " + "   ".join(SIMBOLOS[c] for c in m.resultados)
    pantalla.blit(fuentes.chica.render(texto, True, tema.texto), (x, px(526)))
    _barra_tiempo(pantalla, tema, pygame.Rect(px(140), px(572), px(744), px(10)), max(0.0, 1 - m.t / m.limite))


DIBUJOS = {"ensayo": _dibujar_ensayo, "chat": _dibujar_chat, "mitin": _dibujar_mitin}   # cada minijuego nuevo agrega aqui su dibujo
