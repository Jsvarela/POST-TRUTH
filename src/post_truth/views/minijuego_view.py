"""Vista de los minijuegos: marco comun (titulo, tiempo, pausa y resultado) y el dibujo propio de cada uno."""
import math

import pygame

from post_truth.config import ANCHO, px
from post_truth.models import boca_en_boca as bb
from post_truth.models import rueda_prensa as rp
from post_truth.models.chat import CALMA_LLENA, CARRILES, FILA_SOFI, Chat
from post_truth.models.minijuego import Minijuego, ResultadoMinijuego
from post_truth.models.mitin import CANON as CANON_MITIN, Mitin
from post_truth.models.personaje import Genero, Personaje, Role
from post_truth.views.componentes import Boton, Fuentes, ajustar_texto, panel, recortar
from post_truth.views.escena_view import _dibujar_consecuencias
from post_truth.views.pixel_sprites import cuadro_personaje
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
    teclas = {"chat": "Flechas o A/D: mover a Sofi   |   Espacio: calma",
              "mitin": "Raton o WASD: apuntar   |   1 dato  2 pregunta  3 calma   |   Clic o Espacio: disparar",
              "rueda": "A/D: girar   |   con el marcador en la zona: 1 pista  2 evidencia  3 testimonio  Espacio",
              "boca": "WASD o flechas: moverte   |   Manten E: convencer"}.get(m.id, "1-3: responder")
    ayuda = "Enter: volver a la calle" if resultado else f"{teclas}   |   P: pausa"
    img = fuentes.chica.render(ayuda, True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(10))))


def _dibujar_resultado(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, r: ResultadoMinijuego) -> None:
    caja = pygame.Rect(px(212), px(140), px(600), px(380))
    pygame.draw.rect(pantalla, tema.panel, caja)
    pygame.draw.rect(pantalla, tema.borde, caja, px(2))
    pantalla.blit(fuentes.normal.render(r.texto, True, tema.texto), (caja.x + px(20), caja.y + px(16)))
    _dibujar_consecuencias(pantalla, fuentes, tema, pygame.Rect(caja.x + px(20), caja.y + px(60), caja.w, caja.h), r.impacto)
    color = tema.bueno if r.credibilidad > 0 else tema.malo if r.credibilidad < 0 else tema.texto
    img = fuentes.normal.render(f"Credibilidad {r.credibilidad:+}", True, color)
    pantalla.blit(img, (caja.x + px(20), caja.bottom - px(44)))


def _barra_tiempo(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect, resto: float) -> None:
    pygame.draw.rect(pantalla, tema.panel, rect)
    color = tema.malo if resto < 0.35 else tema.acento
    pygame.draw.rect(pantalla, color, (rect.x, rect.y, round(rect.w * resto), rect.h))


AREA = pygame.Rect(px(212), px(196), px(600), px(364))   # donde ocurre la accion


def _dos_lineas(pantalla: pygame.Surface, fuentes: Fuentes, texto: str, ancho: int, color, x: int, centro_y: int) -> None:
    """Hasta dos lineas centradas en `centro_y`; si sobra, la segunda termina en "..." (letra pixel sin escalar)."""
    lineas = ajustar_texto(texto, fuentes.chica, ancho)
    if len(lineas) > 2:
        lineas = [lineas[0], recortar(" ".join(lineas[1:]), fuentes.chica, ancho)]
    alto = fuentes.chica.get_linesize()
    y = centro_y - alto * len(lineas) // 2
    for linea in lineas:
        pantalla.blit(fuentes.chica.render(linea, True, color), (x, y))
        y += alto


def _texto_corto(fuentes: Fuentes, texto: str, ancho: int, color) -> pygame.Surface:
    return fuentes.chica.render(recortar(texto, fuentes.chica, ancho), True, color)   # sin escalar: letra pixel


def _pj(pantalla: pygame.Surface, tema: Tema, rol: Role, k: int, pies: tuple[int, int], t: float = 0.0,
        animacion: str = "idle_abajo", animo: int = 0, escala: int = 2) -> pygame.Rect:
    """Un personaje pixel (el mismo arte del mundo) con los pies en `pies`; `k` varia genero y apariencia."""
    quien = Personaje(rol, Genero.MUJER if k % 2 else Genero.HOMBRE, (k // 2) % 2)
    img = cuadro_personaje(quien, tema, animacion, int(t * 2) % 2, max(1, round(px(escala))), animo)
    return pantalla.blit(img, img.get_rect(midbottom=pies))


def _rol(m: Minijuego) -> Role:
    """El rol de quien juega (el contexto lo guarda por su nombre)."""
    return next((r for r in Role if r.value == m.contexto.rol), Role.CITIZEN)


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
        pygame.draw.rect(pantalla, tema.panel, caja)
        pygame.draw.rect(pantalla, tema.bueno if apoyo else tema.malo, caja, px(3))
        icono = (caja.x + px(16), caja.centery)
        if apoyo:   # circulo = apoyo; triangulo = ataque (forma, no solo color)
            pygame.draw.circle(pantalla, tema.bueno, icono, px(8))
        else:
            pygame.draw.polygon(pantalla, tema.malo, [(icono[0], icono[1] - px(9)), (icono[0] + px(9), icono[1] + px(7)),
                                                      (icono[0] - px(9), icono[1] + px(7))])
        _dos_lineas(pantalla, fuentes, texto, caja.w - px(34), tema.texto, caja.x + px(28), caja.centery)
    pies = (AREA.x + m.carril * ancho + ancho // 2, AREA.y + round(FILA_SOFI * AREA.h) + px(40))
    pygame.draw.rect(pantalla, tema.acento, (pies[0] - ancho // 2 + px(20), pies[1] + px(2), ancho - px(40), px(4)))
    sofi = _pj(pantalla, tema, Role.CITIZEN, 1, pies, m.t, animo=1 if m.apoyos > m.golpes else -1 if m.golpes else 0,
               escala=3)
    img = fuentes.chica.render("Sofi", True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(sofi.centerx, sofi.top - px(2))))
    _contador(pantalla, fuentes, tema, f"Apoyos {m.apoyos}   Ataques que llegaron {m.golpes}   Borrados {m.borrados}")
    _medidor(pantalla, fuentes, tema, "Calma (Espacio)", m.calma / CALMA_LLENA)
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


NOMBRE_TECLA = {"espacio": "Espacio", "disparo": "Clic"}


def dibujar_tutorial(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, t) -> None:
    """"Como se juega": el minijuego de la demo o la practica, con su cartel, el subtitulo y la tecla que toca."""
    dibujar_minijuego(pantalla, fuentes, tema, t.juego, [], 50, None, False)
    caja = pygame.Rect(0, 0, px(860), px(72))
    caja.midtop = (ANCHO // 2, px(121))   # entre el titulo y el area del juego, tapando la ayuda de siempre
    panel(pantalla, tema, caja, 255, borde=tema.acento)
    titulo = {"demo": "Como se juega: mira la demostracion", "practica": "Ahora tu: practica sin consecuencias",
              "listo": "Listo! Ya sabes jugar"}.get(t.fase, "")
    pantalla.blit(fuentes.normal.render(titulo, True, tema.acento), (caja.x + px(14), caja.y + px(5)))
    texto = (t.paso if t.fase == "demo" else
             f"Aciertos: {min(t.aciertos, 3)} de 3" if t.fase == "practica" else "Ya puedes jugar de verdad.")
    ancho = caja.w - px(160)
    pantalla.blit(fuentes.chica.render(recortar(texto, fuentes.chica, ancho), True, tema.texto),
                  (caja.x + px(14), caja.y + px(30)))
    pie = "Enter: practicar   |   ESC: saltar" if t.fase == "demo" else "Enter: jugar de verdad   |   ESC: saltar"
    pantalla.blit(fuentes.chica.render(pie, True, tema.texto_off), (caja.x + px(14), caja.y + px(50)))
    if t.tecla:   # la tecla que acaba de pulsar la demo, como una tecla de verdad
        tecla = Boton(pygame.Rect(caja.right - px(128), caja.y + px(12), px(112), px(44)),
                      NOMBRE_TECLA.get(t.tecla, t.tecla), lambda: None)
        tecla.foco = True
        tecla.draw(pantalla, fuentes.normal, tema)


def _forma_globo(pantalla: pygame.Surface, tema: Tema, tipo: str, centro: tuple[int, int], r: int,
                hilo: bool = True) -> None:
    x, y = centro
    color = {"dato": tema.acento, "pregunta": tema.detalle, "calma": tema.bueno}[tipo]
    if tipo == "dato":
        pygame.draw.rect(pantalla, color, (x - r, y - r, 2 * r, 2 * r))
    elif tipo == "pregunta":
        pygame.draw.circle(pantalla, color, centro, r)
    else:
        pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    if hilo:
        pygame.draw.line(pantalla, tema.texto_off, (x, y + r), (x, y + r + px(14)), 1)   # el hilo del globo


CIELO = (px(44), px(44))   # el cielo del mitin: entre el escenario (arriba) y la multitud (abajo)


def mitin_a_pantalla(x: float, y: float) -> tuple[int, int]:
    return AREA.x + round(x * AREA.w), AREA.y + CIELO[0] + round(y * (AREA.h - CIELO[0] - CIELO[1]))


def pantalla_a_mitin(pos: tuple[int, int]) -> tuple[float, float] | None:
    """Del raton al area del mitin (None fuera de ella)."""
    if not AREA.collidepoint(pos):
        return None
    return (pos[0] - AREA.x) / AREA.w, (pos[1] - AREA.y - CIELO[0]) / (AREA.h - CIELO[0] - CIELO[1])


def _dibujar_mitin(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, m: Mitin) -> None:
    """Escenario arriba, multitud abajo; los rumores suben zigzagueando y se les dispara desde el canon."""
    panel(pantalla, tema, AREA, 255)
    escenario = pygame.Rect(AREA.x + px(10), AREA.y + px(8), AREA.w - px(20), px(26))
    pygame.draw.rect(pantalla, tema.boton, escenario)
    img = fuentes.chica.render("Arriba: que no lleguen aqui", True, tema.boton_texto)
    pantalla.blit(img, img.get_rect(center=escenario.center))
    animadas = round(16 * m.animo / 100)
    for k in range(16):   # la multitud: animada (circulo) o molesta (cuadrado)
        cx, cy = AREA.x + px(30) + k * px(36), AREA.bottom - px(4)
        gente = _pj(pantalla, tema, (Role.CITIZEN, Role.INFLUENCER, Role.JOURNALIST)[k % 3], k, (cx, cy), m.t + k * 0.3,
                    animo=1 if k < animadas else -1)
        marca = (gente.centerx, gente.top - px(7))   # ademas de la cara: circulo animada, cuadrado molesta
        if k < animadas:
            pygame.draw.circle(pantalla, tema.bueno, marca, px(4))
        else:
            pygame.draw.rect(pantalla, tema.malo, (marca[0] - px(4), marca[1] - px(4), px(8), px(8)))
    for g in m.globos:
        cx, cy = mitin_a_pantalla(*m.posicion(g))
        _forma_globo(pantalla, tema, g[2], (cx, cy), px(18))
        num = fuentes.normal.render({"dato": "1", "pregunta": "2", "calma": "3"}[g[2]], True, tema.fondo)
        pantalla.blit(num, num.get_rect(center=(cx, cy + (px(4) if g[2] == "calma" else 0))))
        _dos_lineas(pantalla, fuentes, g[3], px(140), tema.texto_off, cx - px(70), cy + px(22) + fuentes.chica.get_linesize())
    canon = mitin_a_pantalla(*CANON_MITIN)
    mira = mitin_a_pantalla(*m.mira)
    pygame.draw.line(pantalla, tema.borde, canon, mira, 1)                            # hacia donde apunta
    for b in m.balas:   # el disparo tiene la forma de su municion
        _forma_globo(pantalla, tema, b[4], mitin_a_pantalla(b[0], b[1]), px(6), hilo=False)
    pygame.draw.rect(pantalla, tema.boton, (canon[0] - px(16), canon[1] - px(10), px(32), px(20)))
    _forma_globo(pantalla, tema, m.municion, canon, px(7), hilo=False)
    color = tema.texto if m.recarga <= 0 else tema.texto_off   # la mira se apaga mientras recarga
    pygame.draw.circle(pantalla, color, mira, px(16), px(2))
    pygame.draw.line(pantalla, color, (mira[0] - px(22), mira[1]), (mira[0] + px(22), mira[1]), px(2))
    pygame.draw.line(pantalla, color, (mira[0], mira[1] - px(22)), (mira[0], mira[1] + px(22)), px(2))
    leyenda = pygame.Rect(AREA.x, AREA.bottom + px(22), AREA.w, px(24))
    for i, (tipo, nombre) in enumerate((("dato", "1 dato"), ("pregunta", "2 pregunta"), ("calma", "3 calma"))):
        x = leyenda.x + i * leyenda.w // 3 + px(20)
        if tipo == m.municion:   # la municion cargada, recuadrada (no solo por color)
            pygame.draw.rect(pantalla, tema.acento, (x - px(14), leyenda.y - px(2), px(120), px(26)), px(2))
        _forma_globo(pantalla, tema, tipo, (x, leyenda.centery), px(9), hilo=False)
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
    pygame.draw.rect(pantalla, tema.panel, barra)
    alto = round(barra.h * lleno)
    pygame.draw.rect(pantalla, tema.bueno, (barra.x, barra.bottom - alto, barra.w, alto))
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
        pygame.draw.rect(pantalla, color, (x - r, y - r, 2 * r, 2 * r))
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
    radio = px(228)   # deja arriba el recuadro de la pregunta con su barra
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
        _pj(pantalla, tema, Role.JOURNALIST, i, (c[0], c[1] + px(34)), m.t + i * 0.4, escala=3)   # el periodista
        if p is None:
            continue
        globo = (c[0], c[1] - px(60))                                                  # lo que pide, sobre su cabeza
        pygame.draw.circle(pantalla, tema.fondo, globo, px(18))
        pygame.draw.circle(pantalla, tema.borde, globo, px(18), px(2))
        _icono_prueba(pantalla, tema, p[1], globo, px(10))
        _qte(pantalla, tema, m, p, pygame.Rect(c[0] - px(40), c[1] + px(36), px(80), px(10)))
        if p is apuntada:
            pygame.draw.circle(pantalla, tema.texto, c, px(38), px(3))
    _pj(pantalla, tema, _rol(m), 1, (atril[0], atril[1] + px(10)), m.t, "idle_arriba", escala=3)   # quien responde
    pygame.draw.rect(pantalla, tema.boton, (atril[0] - px(22), atril[1] + px(6), px(44), px(14)))   # el atril
    if apuntada is not None:                                       # lo que pregunta el apuntado y su barra en grande
        caja = pygame.Rect(AREA.x + px(16), AREA.y + px(8), AREA.w - px(32), px(50))
        pygame.draw.rect(pantalla, tema.fondo, caja)
        img = _texto_corto(fuentes, apuntada[2], caja.w - px(20), tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(caja.centerx, caja.y + px(4))))
        _qte(pantalla, tema, m, apuntada, pygame.Rect(caja.centerx - px(180), caja.bottom - px(16), px(360), px(10)))
    leyenda = pygame.Rect(AREA.x, AREA.bottom + px(22), AREA.w, px(24))
    for i, (tipo, nombre) in enumerate((("pista", "1 pista"), ("evidencia", "2 evidencia"), ("testimonio", "3 testimonio"),
                                        ("trampa", "Espacio: sin pruebas"))):
        x = leyenda.x + i * leyenda.w // 4 + px(14)
        tengo = tipo == "trampa" or m.municion[tipo] > 0   # lo que no investigaste se ve apagado y dice "no la tienes"
        _icono_prueba(pantalla, tema, tipo, (x, leyenda.centery), px(8), None if tengo else tema.texto_off)
        texto = nombre if tengo else f"{nombre}: no la tienes"
        pantalla.blit(fuentes.chica.render(texto, True, tema.texto if tengo else tema.texto_off), (x + px(14), leyenda.y + px(2)))
    _contador(pantalla, fuentes, tema, "Responde con lo que investigaste; si no tienes esa prueba, Espacio: no la afirmes")
    _medidor(pantalla, fuentes, tema, "Credito ante la prensa", m.credito / 100)
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  1 - m.respondidas / m.total)                     # sin reloj: lo que falta por responder


def _qte(pantalla: pygame.Surface, tema: Tema, m: rp.RuedaPrensa, p: list, barra: pygame.Rect) -> None:
    """Quick time event: la zona (bueno) y el marcador que va y vuelve; dentro, la tecla cuenta."""
    pygame.draw.rect(pantalla, tema.panel, barra)
    pygame.draw.rect(pantalla, tema.borde, barra, px(2))
    zona = pygame.Rect(0, barra.y, round(barra.w * m.ancho_zona), barra.h)
    zona.centerx = barra.x + round(barra.w * p[4])
    pygame.draw.rect(pantalla, tema.bueno, zona)
    x = barra.x + round(barra.w * m.marcador(p))
    color = tema.texto if m.en_zona(p) else tema.malo
    pygame.draw.rect(pantalla, color, (x - px(3), barra.y - px(4), px(6), barra.h + px(8)))   # forma: barra vertical


ALTO_BARRIO = AREA.h - px(150)   # el barrio arriba; abajo queda el cuadro de la charla


def _en_area(pos) -> tuple[int, int]:
    return AREA.x + px(30) + round(pos[0] * (AREA.w - px(60))), AREA.y + px(24) + round(pos[1] * ALTO_BARRIO)


def _cabe(fuentes: Fuentes, texto: str, ancho: int, color) -> pygame.Surface:
    """El texto completo si cabe; si no, recortado con "..." (escalar la letra pixel la deja borrosa)."""
    return fuentes.chica.render(recortar(texto, fuentes.chica, ancho), True, color)


def _casa(pantalla: pygame.Surface, tema: Tema, estado: str, c: tuple[int, int]) -> None:
    """Casa por forma segun lo que cree: cuadrado vacio no sabe, triangulo lo cree, circulo convencida, X enojada."""
    x, y = c
    pared = pygame.Rect(x - px(20), y - px(4), px(40), px(24))   # la casa pixel; encima, su estado por forma
    pygame.draw.rect(pantalla, tema.boton, pared)
    pygame.draw.rect(pantalla, tema.fondo, pared, px(2))
    for k in range(5):   # techo escalonado
        pygame.draw.rect(pantalla, tema.borde, (x - px(24) + k * px(5), y - px(8) - k * px(4), px(48) - k * px(10), px(4)))
    pygame.draw.rect(pantalla, tema.fondo, (x - px(4), y + px(8), px(8), px(12)))   # la puerta
    y -= px(40)
    c = (x, y)
    r = px(11)
    if estado == bb.SIN:
        pygame.draw.rect(pantalla, tema.texto_off, (x - r, y - r, 2 * r, 2 * r), px(3))
    elif estado == bb.CREE:
        pygame.draw.polygon(pantalla, tema.malo, [(x, y - r), (x + r, y + r), (x - r, y + r)])
    elif estado == bb.CONVENCIDA:
        pygame.draw.circle(pantalla, tema.bueno, c, r)
    else:
        pygame.draw.rect(pantalla, tema.malo, (x - r, y - r, 2 * r, 2 * r))
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
    _pj(pantalla, tema, _rol(m), 1, (yo[0], yo[1] + px(20)), m.t)
    if m.charla is not None:
        casa, pers = m.charla
        c = centros[casa]
        caja = pygame.Rect(AREA.x + px(16), AREA.bottom - px(84), AREA.w - px(32), px(74))
        pygame.draw.rect(pantalla, tema.fondo, caja)
        pygame.draw.circle(pantalla, tema.acento, (c[0], c[1] - px(10)), px(40), px(3))   # con quien hablas
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
            pygame.draw.rect(pantalla, tema.panel, barra)
            pygame.draw.rect(pantalla, tema.bueno, (barra.x, barra.y, round(barra.w * lleno), barra.h))
    _contador(pantalla, fuentes, tema, f"\"{m.rumor}\"   |   Convencidos {m.contar(bb.CONVENCIDA)}   Lo creen "
                                       f"{m.contar(bb.CREE)}   Enojados {m.contar(bb.ENOJADA)}")
    _barra_tiempo(pantalla, tema, pygame.Rect(AREA.x, AREA.bottom + px(8), AREA.w, px(8)),
                  max(0.0, 1 - m.t / m.duracion))


DIBUJOS = {"chat": _dibujar_chat, "mitin": _dibujar_mitin, "rueda": _dibujar_rueda,
           "boca": _dibujar_boca}   # cada minijuego nuevo agrega aqui su dibujo
