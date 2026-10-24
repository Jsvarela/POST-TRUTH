"""Vista de los minijuegos: marco comun (titulo, tiempo, pausa y resultado) y el dibujo propio de cada uno."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.chat import CALMA_LLENA, CARRILES, FILA_SOFI, Chat
from post_truth.models.minijuego import Ensayo, Minijuego, ResultadoMinijuego
from post_truth.models.mitin import COLUMNAS, Mitin
from post_truth.views.componentes import Fuentes, ajustar_texto, panel
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
    teclas = {"ensayo": "1-2: responder", "chat": "Flechas o A/D: mover a Sofi   |   Espacio: calma",
              "mitin": "1 dato   2 pregunta   3 calma"}.get(m.id, "1-3: responder")
    ayuda = "Enter: volver a la calle" if resultado else f"{teclas}   |   P: pausa"
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


AREA = pygame.Rect(px(212), px(196), px(600), px(364))   # donde ocurre la accion


def _texto_corto(fuentes: Fuentes, texto: str, ancho: int, color) -> pygame.Surface:
    img = fuentes.chica.render(texto if len(texto) <= 34 else texto[:33] + "...", True, color)
    if img.get_width() > ancho:
        img = pygame.transform.smoothscale(img, (ancho, img.get_height()))
    return img


def _dibujar_chat(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Chat) -> None:
    """Tres carriles; los mensajes caen y Sofi (abajo) los atrapa o los esquiva."""
    panel(pantalla, tema, AREA, 255)
    ancho = AREA.w // CARRILES
    for k in range(1, CARRILES):
        x = AREA.x + k * ancho
        pygame.draw.line(pantalla, tema.borde, (x, AREA.y + px(10)), (x, AREA.bottom - px(10)), 1)
    for carril, altura, tipo, texto in m.mensajes:
        cx, cy = AREA.x + carril * ancho + ancho // 2, AREA.y + round(altura * AREA.h)
        caja = pygame.Rect(0, 0, ancho - px(16), px(46))
        caja.center = (cx, cy)
        apoyo = tipo == "apoyo"
        pygame.draw.rect(pantalla, tema.panel, caja, border_radius=px(10))
        pygame.draw.rect(pantalla, tema.bueno if apoyo else tema.malo, caja, px(3), border_radius=px(10))
        icono = (caja.x + px(16), caja.centery)
        if apoyo:   # circulo = apoyo; triangulo = ataque (forma, no solo color)
            pygame.draw.circle(pantalla, tema.bueno, icono, px(8))
        else:
            pygame.draw.polygon(pantalla, tema.malo, [(icono[0], icono[1] - px(9)), (icono[0] + px(9), icono[1] + px(7)),
                                                      (icono[0] - px(9), icono[1] + px(7))])
        pantalla.blit(_texto_corto(fuentes, texto, caja.w - px(34), tema.texto),
                      (caja.x + px(28), caja.centery - fuentes.chica.get_height() // 2))
    sofi = pygame.Rect(0, 0, ancho - px(40), px(34))
    sofi.center = (AREA.x + m.carril * ancho + ancho // 2, AREA.y + round(FILA_SOFI * AREA.h))
    pygame.draw.rect(pantalla, tema.acento, sofi, border_radius=px(17))
    img = fuentes.normal.render("Sofi", True, tema.boton_texto)
    pantalla.blit(img, img.get_rect(center=sofi.center))
    _contador(pantalla, fuentes, tema, f"Apoyos {m.apoyos}   Ataques que llegaron {m.golpes}   Borrados {m.borrados}")
    _medidor(pantalla, fuentes, tema, "Calma (Espacio)", m.calma / CALMA_LLENA)
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


def _forma_globo(pantalla: pygame.Surface, tema: Tema, tipo: str, centro: tuple[int, int], r: int) -> None:
    x, y = centro
    color = {"dato": tema.acento, "pregunta": tema.detalle, "calma": tema.bueno}[tipo]
    if tipo == "dato":
        pygame.draw.rect(pantalla, color, (x - r, y - r, 2 * r, 2 * r), border_radius=px(4))
    elif tipo == "pregunta":
        pygame.draw.circle(pantalla, color, centro, r)
    else:
        pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    pygame.draw.line(pantalla, tema.texto_off, (x, y + r), (x, y + r + px(14)), 1)   # el hilo del globo


def _dibujar_mitin(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Mitin) -> None:
    """Escenario arriba, multitud abajo; los rumores suben como globos."""
    panel(pantalla, tema, AREA, 255)
    escenario = pygame.Rect(AREA.x + px(10), AREA.y + px(8), AREA.w - px(20), px(26))
    pygame.draw.rect(pantalla, tema.boton, escenario, border_radius=px(8))
    img = fuentes.chica.render("Escenario: que no lleguen aqui", True, tema.boton_texto)
    pantalla.blit(img, img.get_rect(center=escenario.center))
    animadas = round(16 * m.animo / 100)
    for k in range(16):   # la multitud: animada (circulo) o molesta (cuadrado)
        cx, cy = AREA.x + px(30) + k * px(36), AREA.bottom - px(18)
        if k < animadas:
            pygame.draw.circle(pantalla, tema.bueno, (cx, cy), px(9))
        else:
            pygame.draw.rect(pantalla, tema.malo, (cx - px(8), cy - px(8), px(16), px(16)), border_radius=px(3))
    ancho = AREA.w // COLUMNAS
    alto_util = AREA.h - px(80)
    for columna, altura, tipo, grito in m.globos:
        cx = AREA.x + columna * ancho + ancho // 2
        cy = escenario.bottom + px(20) + round(altura * alto_util)
        _forma_globo(pantalla, tema, tipo, (cx, cy), px(18))
        num = fuentes.normal.render({"dato": "1", "pregunta": "2", "calma": "3"}[tipo], True, tema.fondo)
        pantalla.blit(num, num.get_rect(center=(cx, cy + (px(4) if tipo == "calma" else 0))))
        pantalla.blit(_texto_corto(fuentes, grito, ancho - px(6), tema.texto_off),
                      (cx - (ancho - px(6)) // 2, cy + px(22)))
    leyenda = pygame.Rect(AREA.x, AREA.bottom + px(22), AREA.w, px(24))
    for i, (tipo, nombre) in enumerate((("dato", "1 dato"), ("pregunta", "2 pregunta"), ("calma", "3 calma"))):
        x = leyenda.x + i * leyenda.w // 3 + px(20)
        _forma_globo(pantalla, tema, tipo, (x, leyenda.centery), px(9))
        pantalla.blit(fuentes.chica.render(nombre, True, tema.texto), (x + px(16), leyenda.y + px(2)))
    _contador(pantalla, fuentes, tema, f"Animo de la multitud {round(m.animo)}   |   Evidencia reunida: "
                                       f"{m.contexto.evidencias}")
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


def _contador(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, texto: str) -> None:
    img = fuentes.chica.render(texto, True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, AREA.y - px(4))))


def _medidor(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, nombre: str, lleno: float) -> None:
    barra = pygame.Rect(AREA.right + px(20), AREA.y + px(40), px(22), AREA.h - px(80))
    pygame.draw.rect(pantalla, tema.panel, barra, border_radius=px(11))
    alto = round(barra.h * lleno)
    pygame.draw.rect(pantalla, tema.bueno, (barra.x, barra.bottom - alto, barra.w, alto), border_radius=px(11))
    img = fuentes.chica.render("Lista!" if lleno >= 1 else nombre.split(" ")[0], True,
                               tema.bueno if lleno >= 1 else tema.texto)
    pantalla.blit(img, img.get_rect(midtop=(barra.centerx, barra.bottom + px(4))))


DIBUJOS = {"ensayo": _dibujar_ensayo, "chat": _dibujar_chat, "mitin": _dibujar_mitin}   # cada minijuego nuevo agrega aqui su dibujo
