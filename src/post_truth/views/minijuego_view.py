"""Vista de los minijuegos: marco comun (titulo, tiempo, pausa y resultado) y el dibujo propio de cada uno."""
import math

import pygame

from post_truth.config import ANCHO, px
from post_truth.models import boca_en_boca as bb
from post_truth.models import rueda_prensa as rp
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
              "mitin": "1 dato   2 pregunta   3 calma",
              "rueda": "A/D o flechas: girar   |   1 pista  2 evidencia  3 testimonio  Espacio: sin pruebas",
              "boca": "WASD o flechas: moverte   |   Manten E: convencer"}.get(m.id, "1-3: responder")
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


def _icono_prueba(pantalla: pygame.Surface, tema: Tema, tipo: str, centro: tuple[int, int], r: int, color=None) -> None:
    """Forma por tipo de prueba (no solo color): triangulo pista, cuadrado evidencia, circulo testimonio, X trampa."""
    x, y = centro
    color = color or {"pista": tema.acento, "evidencia": tema.detalle, "testimonio": tema.bueno, "trampa": tema.malo}[tipo]
    if tipo == "pista":
        pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    elif tipo == "evidencia":
        pygame.draw.rect(pantalla, color, (x - r, y - r, 2 * r, 2 * r), border_radius=px(3))
    elif tipo == "testimonio":
        pygame.draw.circle(pantalla, color, centro, r)
    else:
        pygame.draw.line(pantalla, color, (x - r, y - r), (x + r, y + r), px(5))
        pygame.draw.line(pantalla, color, (x - r, y + r), (x + r, y - r), px(5))


def _angulo(pos: float) -> float:
    """-1 (izquierda) .. 1 (derecha) en el arco de periodistas (de 160 a 20 grados: los extremos no tocan el borde)."""
    return math.pi * (0.89 - 0.78 * (pos + 1) / 2)


def _dibujar_rueda(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: rp.RuedaPrensa) -> None:
    """El atril abajo; los periodistas en semicirculo; el foco gira y el anillo de cada pregunta se cierra."""
    panel(pantalla, tema, AREA, 255)
    atril = (AREA.centerx, AREA.bottom - px(36))
    radio = px(250)
    a = _angulo(m.foco)
    punta = (atril[0] + round(radio * math.cos(a)), atril[1] - round(radio * math.sin(a)))
    pygame.draw.line(pantalla, tema.acento, atril, punta, px(6))                      # el foco
    apuntada = m.apuntada()
    preguntas = {p[0]: p for p in m.preguntas}
    for i in range(rp.PERIODISTAS):
        b = _angulo(rp.posicion(i))
        c = (atril[0] + round(radio * math.cos(b)), atril[1] - round(radio * math.sin(b)))
        pygame.draw.circle(pantalla, tema.panel, c, px(30))
        pygame.draw.circle(pantalla, tema.borde, c, px(30), px(2))
        p = preguntas.get(i)
        if p is None:
            pygame.draw.circle(pantalla, tema.texto_off, c, px(8))                     # periodista esperando
            continue
        resto = max(0.0, p[3] / p[4])
        color = tema.malo if resto < 0.35 else tema.acento
        caja = pygame.Rect(0, 0, px(72), px(72))
        caja.center = c
        pygame.draw.arc(pantalla, color, caja, math.pi / 2, math.pi / 2 + 2 * math.pi * resto, px(6))   # su tiempo
        _icono_prueba(pantalla, tema, p[1], c, px(16))
        if p is apuntada:
            pygame.draw.circle(pantalla, tema.texto, c, px(38), px(3))
    pygame.draw.circle(pantalla, tema.boton, atril, px(22))
    img = fuentes.chica.render("Tu", True, tema.boton_texto)
    pantalla.blit(img, img.get_rect(center=atril))
    if apuntada is not None:                                                         # lo que pregunta el apuntado
        caja = pygame.Rect(AREA.x + px(16), AREA.y + px(10), AREA.w - px(32), px(32))
        pygame.draw.rect(pantalla, tema.fondo, caja, border_radius=px(8))
        img = _texto_corto(fuentes, apuntada[2], caja.w - px(20), tema.texto)
        pantalla.blit(img, img.get_rect(center=caja.center))
    leyenda = pygame.Rect(AREA.x, AREA.bottom + px(22), AREA.w, px(24))
    for i, (tipo, nombre) in enumerate((("pista", f"1 pista x{m.municion['pista']}"),
                                        ("evidencia", f"2 evidencia x{m.municion['evidencia']}"),
                                        ("testimonio", f"3 testimonio x{m.municion['testimonio']}"),
                                        ("trampa", "Espacio: sin pruebas"))):
        x = leyenda.x + i * leyenda.w // 4 + px(14)
        _icono_prueba(pantalla, tema, tipo, (x, leyenda.centery), px(8))
        pantalla.blit(fuentes.chica.render(nombre, True, tema.texto), (x + px(14), leyenda.y + px(2)))
    _contador(pantalla, fuentes, tema, "Tu municion es lo que investigaste: cada respuesta gasta una prueba")
    _medidor(pantalla, fuentes, tema, "Credito ante la prensa", m.credito / 100)
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


ALTO_BARRIO = AREA.h - px(150)   # el barrio arriba; abajo queda el cuadro de la charla


def _en_area(pos) -> tuple[int, int]:
    return AREA.x + px(30) + round(pos[0] * (AREA.w - px(60))), AREA.y + px(24) + round(pos[1] * ALTO_BARRIO)


def _cabe(fuentes: Fuentes, texto: str, ancho: int, color) -> pygame.Surface:
    """El texto completo; si no cabe, se angosta un poco (no se corta)."""
    img = fuentes.chica.render(texto, True, color)
    return pygame.transform.smoothscale(img, (ancho, img.get_height())) if img.get_width() > ancho else img


def _casa(pantalla: pygame.Surface, tema: Tema, estado: str, c: tuple[int, int]) -> None:
    """Casa por forma segun lo que cree: cuadrado vacio no sabe, triangulo lo cree, circulo convencida, X enojada."""
    x, y = c
    r = px(18)
    if estado == bb.SIN:
        pygame.draw.rect(pantalla, tema.texto_off, (x - r, y - r, 2 * r, 2 * r), px(3), border_radius=px(4))
    elif estado == bb.CREE:
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    elif estado == bb.CONVENCIDA:
        pygame.draw.circle(pantalla, tema.bueno, c, r)
    else:
        pygame.draw.rect(pantalla, tema.malo, (x - r, y - r, 2 * r, 2 * r), border_radius=px(4))
        pygame.draw.line(pantalla, tema.fondo, (x - r // 2, y - r // 2), (x + r // 2, y + r // 2), px(4))
        pygame.draw.line(pantalla, tema.fondo, (x - r // 2, y + r // 2), (x + r // 2, y - r // 2), px(4))


def _dibujar_boca(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: bb.BocaEnBoca) -> None:
    """El barrio como grafo: casas (vertices) y calles (aristas); el chisme salta por ellas."""
    panel(pantalla, tema, AREA, 255)
    casas = bb.datos()["casas"]
    centros = [_en_area(c["pos"]) for c in casas]
    for a, b in bb.datos()["conexiones"]:
        pygame.draw.line(pantalla, tema.borde, centros[a], centros[b], px(3))
    fase = (m.t % m.intervalo) / m.intervalo
    for a, b in m.saltos[-1:]:   # el ultimo salto: un punto que viaja por la calle
        x = centros[a][0] + (centros[b][0] - centros[a][0]) * min(1.0, fase * 2)
        y = centros[a][1] + (centros[b][1] - centros[a][1]) * min(1.0, fase * 2)
        if fase < 0.5:
            pygame.draw.circle(pantalla, tema.malo, (round(x), round(y)), px(6))
    for i, (c, estado) in enumerate(zip(centros, m.casas)):
        _casa(pantalla, tema, estado, c)
        img = fuentes.chica.render(casas[i]["nombre"], True, tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(c[0], c[1] + px(22))))
    yo = _en_area(m.jugador)
    pygame.draw.circle(pantalla, tema.borde, yo, round(bb.datos()["radio"] * (AREA.w - px(60))), 1)   # hasta donde se habla
    pygame.draw.circle(pantalla, tema.acento, yo, px(14))
    img = fuentes.chica.render("Tu", True, tema.boton_texto)
    pantalla.blit(img, img.get_rect(center=yo))
    if m.charla is not None:
        casa, pers = m.charla
        c = centros[casa]
        caja = pygame.Rect(AREA.x + px(16), AREA.bottom - px(84), AREA.w - px(32), px(74))
        pygame.draw.rect(pantalla, tema.fondo, caja, border_radius=px(10))
        pygame.draw.circle(pantalla, tema.acento, c, px(26), px(3))   # con quien hablas
        nodo, opcion = pers.nodo, pers.opcion
        if nodo is not None and opcion is not None:
            fuerza = {"evidencia": "con evidencia: rapido", "credibilidad": "por tu credibilidad",
                      "nada": "sin pruebas: lento, no lo sueltes"}[opcion.tipo]
            pantalla.blit(_cabe(fuentes, f"{casas[casa]['nombre']}: {nodo.texto}", caja.w - px(20), tema.texto),
                          (caja.x + px(10), caja.y + px(6)))
            pantalla.blit(_cabe(fuentes, f"Tu ({fuerza}): {opcion.texto}", caja.w - px(20), tema.acento),
                          (caja.x + px(10), caja.y + px(28)))
            barra = pygame.Rect(caja.x + px(10), caja.bottom - px(16), caja.w - px(20), px(8))
            lleno = (len(pers.camino) + pers.progreso) / 3   # 3 etapas: la profundidad del arbol
            pygame.draw.rect(pantalla, tema.panel, barra, border_radius=barra.h // 2)
            pygame.draw.rect(pantalla, tema.bueno, (barra.x, barra.y, round(barra.w * lleno), barra.h),
                             border_radius=barra.h // 2)
    _contador(pantalla, fuentes, tema, f"\"{m.rumor}\"   |   Convencidos {m.contar(bb.CONVENCIDA)}   Lo creen "
                                       f"{m.contar(bb.CREE)}   Enojados {m.contar(bb.ENOJADA)}")
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


DIBUJOS = {"ensayo": _dibujar_ensayo, "chat": _dibujar_chat, "mitin": _dibujar_mitin, "rueda": _dibujar_rueda,
           "boca": _dibujar_boca}   # cada minijuego nuevo agrega aqui su dibujo
