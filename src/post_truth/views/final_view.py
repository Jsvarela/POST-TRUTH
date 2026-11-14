"""El final en diapositivas: una por dia (que publico @VerdadNova, que hiciste, si estuvo bien o mal, a quien afecto,
cuantos lo creyeron y como cambio la ciudad) y una con la grafica de votos. Mas formas que texto; todo se distingue
por forma y no solo por color. Solo lee la bitacora de la sesion."""
import pygame

from post_truth.config import ANCHO, px
from post_truth.models.eleccion import VEREDICTO, ResultadoEleccion
from post_truth.models.reparto import Candidato
from post_truth.views import hud
from post_truth.views.componentes import Fuentes, ajustar_texto, panel, recortar
from post_truth.views.retrato_view import dibujar_retrato
from post_truth.views.theme import TOKENS, Tema, esp

CAJA = pygame.Rect(px(48), px(96), ANCHO - px(96), px(470))
ACCION = {"compartir": "Compartiste", "verificar": "Verificaste", "ignorar": "Ignoraste", "reportar": "Reportaste",
          "vencido": "No decidiste"}
INDICADORES = (("misinformation", "Desinformacion", "Desinfo."), ("trust", "Confianza ciudadana", "Confianza"),
               ("conflicts", "Conflictos", "Conflictos"), ("verified_information", "Informacion verificada", "Verificada"))
FINALES = {"final_informada": "Ciudad informada", "final_dividida": "Ciudad dividida",
           "final_enganada": "Ciudad engañada"}
GENTE = 20   # "la red lo creyo": 20 personitas


def veredicto(b: dict) -> tuple[str, str]:
    """("bien" | "regular" | "mal", la razon corta)."""
    texto = VEREDICTO[(b["falsa"], b["accion"])]
    nivel, razon = texto.split(": ", 1)
    return nivel.lower(), razon


def _flecha(pantalla, color, centro: tuple[int, int], arriba: bool, largo: int) -> None:
    x, y = centro
    s = -1 if arriba else 1
    pygame.draw.rect(pantalla, color, (x - px(5), min(y, y + s * largo), px(10), largo))
    punta = y + s * (largo + px(12))
    pygame.draw.polygon(pantalla, color, [(x - px(14), y + s * largo), (x + px(14), y + s * largo), (x, punta)])


def _icono_accion(pantalla, tema: Tema, accion: str, c: tuple[int, int], r: int) -> None:
    """Forma propia por accion: flecha (compartir), lupa (verificar), raya (ignorar), bandera (reportar), reloj."""
    x, y = c
    color = tema.texto
    if accion == "compartir":
        pygame.draw.polygon(pantalla, color, [(x - r, y + r // 3), (x + r // 3, y + r // 3), (x + r // 3, y + r),
                                              (x + r, y), (x + r // 3, y - r), (x + r // 3, y - r // 3), (x - r, y - r // 3)])
    elif accion == "verificar":
        pygame.draw.circle(pantalla, color, (x - r // 4, y - r // 4), r * 2 // 3, px(6))
        pygame.draw.line(pantalla, color, (x + r // 4, y + r // 4), (x + r, y + r), px(8))
    elif accion == "ignorar":
        pygame.draw.rect(pantalla, color, (x - r, y - px(6), 2 * r, px(12)))
    elif accion == "reportar":
        pygame.draw.rect(pantalla, color, (x - r, y - r, px(8), 2 * r))
        pygame.draw.polygon(pantalla, color, [(x - r + px(8), y - r), (x + r, y - r // 2), (x - r + px(8), y)])
    else:
        pygame.draw.circle(pantalla, color, c, r, px(6))
        pygame.draw.line(pantalla, color, c, (x, y - r * 2 // 3), px(6))
        pygame.draw.line(pantalla, color, c, (x + r // 2, y), px(6))


def _sello(pantalla, tema: Tema, nivel: str, c: tuple[int, int], r: int) -> None:
    """Visto en circulo (bien), rombo (regular), cruz en cuadrado (mal)."""
    x, y = c
    if nivel == "bien":
        pygame.draw.circle(pantalla, tema.bueno, c, r)
        pygame.draw.lines(pantalla, tema.fondo, False, [(x - r // 2, y), (x - r // 8, y + r // 2), (x + r // 2, y - r // 2)], px(6))
    elif nivel == "regular":
        pygame.draw.polygon(pantalla, tema.acento, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
        pygame.draw.rect(pantalla, tema.fondo, (x - r // 2, y - px(4), r, px(8)))
    else:
        pygame.draw.rect(pantalla, tema.malo, (x - r, y - r, 2 * r, 2 * r))
        pygame.draw.line(pantalla, tema.fondo, (x - r // 2, y - r // 2), (x + r // 2, y + r // 2), px(6))
        pygame.draw.line(pantalla, tema.fondo, (x - r // 2, y + r // 2), (x + r // 2, y - r // 2), px(6))


def _personita(pantalla, color, c: tuple[int, int], llena: bool) -> None:
    x, y = c
    ancho = 0 if llena else px(2)
    pygame.draw.circle(pantalla, color, (x, y - px(9)), px(5), ancho)
    pygame.draw.rect(pantalla, color, (x - px(6), y - px(3), px(12), px(14)), ancho)


def _pie(pantalla, fuentes: Fuentes, tema: Tema, i: int, total: int) -> None:
    for k in range(total):   # en que diapositiva va: un cuadro por cada una
        r = pygame.Rect(0, 0, px(12), px(12))
        r.center = (ANCHO // 2 + (k - (total - 1) / 2) * px(22), CAJA.bottom + px(22))
        pygame.draw.rect(pantalla, tema.acento if k == i else tema.borde, r, 0 if k == i else px(2))
    texto = "Flechas o Enter: siguiente   |   ESC: volver al menu"
    img = fuentes.chica.render(texto, True, tema.texto)
    pantalla.blit(img, img.get_rect(midbottom=(ANCHO // 2, pantalla.get_height() - px(14))))


def dibujar_dia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, b: dict, candidatos: list[Candidato],
                i: int, total: int) -> None:
    pantalla.fill(tema.fondo)
    titulo = fuentes.titulo.render(f"Dia {b['dia']}", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(28))))
    panel(pantalla, tema, CAJA, TOKENS.alfa_panel)
    x0 = CAJA.x + esp(4)
    # arriba: el rumor y si era falso
    sello = "FALSO" if b["falsa"] else "CIERTO"
    img = fuentes.normal.render(sello, True, tema.fondo)
    caja_sello = img.get_rect().inflate(esp(3) * 2, esp(1) * 2)
    caja_sello.topright = (CAJA.right - esp(4), CAJA.y + esp(3))
    pygame.draw.rect(pantalla, tema.malo if b["falsa"] else tema.bueno, caja_sello)
    pantalla.blit(img, img.get_rect(center=caja_sello.center))
    rumor = recortar(f"\"{b['titulo']}\"", fuentes.grande, caja_sello.x - x0 - esp(3))
    pantalla.blit(fuentes.grande.render(rumor, True, tema.texto), (x0, CAJA.y + esp(2)))
    # a la izquierda: lo que hiciste y el veredicto
    nivel, razon = veredicto(b)
    centro = (x0 + px(70), CAJA.y + px(150))
    _icono_accion(pantalla, tema, b["accion"], centro, px(34))
    pantalla.blit(fuentes.normal.render(ACCION[b["accion"]], True, tema.texto),
                  fuentes.normal.render(ACCION[b["accion"]], True, tema.texto).get_rect(midtop=(centro[0], centro[1] + px(46))))
    _sello(pantalla, tema, nivel, (centro[0] + px(120), centro[1]), px(30))
    pantalla.blit(fuentes.normal.render(nivel.capitalize(), True, tema.texto),
                  fuentes.normal.render(nivel.capitalize(), True, tema.texto).get_rect(midtop=(centro[0] + px(120), centro[1] + px(46))))
    for k, linea in enumerate(ajustar_texto(razon, fuentes.chica, px(300))[:2]):
        pantalla.blit(fuentes.chica.render(linea, True, tema.texto_off), (x0, centro[1] + px(84) + k * px(18)))
    # a la derecha: a quien afecto
    afectados = [(c, b["apoyo"][c.id]) for c in candidatos if b["apoyo"].get(c.id)]
    ax = CAJA.x + px(420)
    if not afectados:
        pantalla.blit(fuentes.chica.render("No tocaba a ningun candidato", True, tema.texto_off), (ax, centro[1]))
    for k, (c, d) in enumerate(afectados[:3]):
        r = pygame.Rect(ax + k * px(150), CAJA.y + px(84), px(80), px(96))
        dibujar_retrato(pantalla, c.personaje, tema, r)
        _flecha(pantalla, tema.bueno if d > 0 else tema.malo, (r.right + px(26), r.centery + (px(20) if d > 0 else -px(20))),
                d > 0, px(18) if abs(d) < 5 else px(34))
        nombre = recortar(c.nombre.split()[0], fuentes.chica, px(120))
        pantalla.blit(fuentes.chica.render(nombre, True, tema.texto), (r.x, r.bottom + px(6)))
    # abajo: cuantos lo creyeron (personitas) y la ciudad (iconos con flecha)
    y = CAJA.y + px(300)
    if b.get("creyeron") is not None:
        pantalla.blit(fuentes.chica.render("La red lo creyo", True, tema.texto), (x0, y))
        llenas = round(GENTE * b["creyeron"] / 100)
        for k in range(GENTE):
            _personita(pantalla, tema.malo if k < llenas else tema.texto_off, (x0 + px(10) + k * px(22), y + px(46)), k < llenas)
    cx = CAJA.x + px(560)
    pantalla.blit(fuentes.chica.render("La ciudad", True, tema.texto), (cx, y))
    for k, (clave, nombre, corto) in enumerate(INDICADORES):
        d = b.get("ciudad", {}).get(clave, 0)
        c = (cx + px(16) + k * px(86), y + px(50))
        hud.icono(pantalla, tema, nombre, c, px(12))
        if d:
            malo = (d > 0) == (clave in ("misinformation", "conflicts"))
            _flecha(pantalla, tema.malo if malo else tema.bueno, (c[0] + px(26), c[1] + (px(12) if d > 0 else -px(12))),
                    d > 0, px(10))
        pantalla.blit(fuentes.chica.render(corto, True, tema.texto_off),
                      fuentes.chica.render(corto, True, tema.texto_off).get_rect(midtop=(c[0], c[1] + px(26))))
    _pie(pantalla, fuentes, tema, i, total)


def dibujar_votos(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, r: ResultadoEleccion,
                  candidatos: list[Candidato], final: str, i: int, total: int) -> None:
    """La grafica: votos de cada uno (lleno) contra los que habria tenido sin los rumores falsos (contorno)."""
    pantalla.fill(tema.fondo)
    titulo = fuentes.titulo.render("La eleccion", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(28))))
    panel(pantalla, tema, CAJA, TOKENS.alfa_panel)
    etiqueta = FINALES.get(final, "")
    if etiqueta:
        img = fuentes.normal.render(etiqueta, True, tema.fondo)
        chip = img.get_rect().inflate(esp(3) * 2, esp(1) * 2)
        chip.topright = (CAJA.right - esp(4), CAJA.y + esp(3))
        pygame.draw.rect(pantalla, tema.acento, chip)
        pantalla.blit(img, img.get_rect(center=chip.center))
    maximo = max([*r.votos.values(), *r.sin_rumores.values(), 1])
    largo = CAJA.w - px(330)
    for k, c in enumerate(candidatos):
        y = CAJA.y + px(70) + k * px(86)
        dibujar_retrato(pantalla, c.personaje, tema, pygame.Rect(CAJA.x + esp(4), y, px(60), px(72)))
        pantalla.blit(fuentes.chica.render(c.nombre, True, tema.texto), (CAJA.x + px(84), y + px(4)))
        x = CAJA.x + px(84)
        lleno = pygame.Rect(x, y + px(28), round(largo * r.votos[c.id] / maximo), px(22))
        pygame.draw.rect(pantalla, tema.acento if c.id == r.ganador else tema.borde, lleno)
        if r.sin_rumores:   # sin los rumores falsos: solo el contorno (se ve cuanto le sumaron o le quitaron)
            sin = pygame.Rect(x, y + px(24), round(largo * r.sin_rumores[c.id] / maximo), px(30))
            pygame.draw.rect(pantalla, tema.texto, sin, px(2))
        pantalla.blit(fuentes.normal.render(f"{r.votos[c.id]:.0f}%", True, tema.texto), (x + largo + px(12), y + px(26)))
        if c.id == r.ganador:   # corona: no depende solo del color
            cx = x + largo + px(80)
            pygame.draw.polygon(pantalla, tema.detalle, [(cx - px(14), y + px(46)), (cx - px(14), y + px(30)),
                                                         (cx - px(7), y + px(38)), (cx, y + px(26)), (cx + px(7), y + px(38)),
                                                         (cx + px(14), y + px(30)), (cx + px(14), y + px(46))])
    ley = CAJA.bottom - px(40)
    pygame.draw.rect(pantalla, tema.borde, (CAJA.x + esp(4), ley, px(28), px(14)))
    pantalla.blit(fuentes.chica.render("votos", True, tema.texto), (CAJA.x + esp(4) + px(36), ley - px(2)))
    pygame.draw.rect(pantalla, tema.texto, (CAJA.x + px(180), ley - px(2), px(28), px(18)), px(2))
    pantalla.blit(fuentes.chica.render("sin los rumores falsos", True, tema.texto), (CAJA.x + px(216), ley - px(2)))
    _pie(pantalla, fuentes, tema, i, total)


ESTRELLAS = {"oro": 3, "plata": 2, "bronce": 1}


def _estrella(pantalla, color, c: tuple[int, int], r: int) -> None:
    """Estrella pixel: un rombo con cuatro puntas (forma, no solo color)."""
    x, y = c
    pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r // 3, y - r // 3), (x + r, y), (x + r // 3, y + r // 3),
                                          (x, y + r), (x - r // 3, y + r // 3), (x - r, y), (x - r // 3, y - r // 3)])


def dibujar_medalla(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, total: int, medalla: str,
                    desglose: list[tuple[str, int, int]], i: int, paginas: int, tabla: list[dict] | None = None,
                    iniciales: str | None = None) -> None:
    """La ultima diapositiva: el puntaje de la campaña, su medalla (1 a 3 estrellas) y de donde salio cada punto."""
    pantalla.fill(tema.fondo)
    titulo = fuentes.titulo.render("Tu campaña", True, tema.acento)
    pantalla.blit(titulo, titulo.get_rect(midtop=(ANCHO // 2, px(28))))
    panel(pantalla, tema, CAJA, TOKENS.alfa_panel)
    cx, cy = CAJA.x + px(190), CAJA.y + px(190)
    color = {"oro": tema.acento, "plata": tema.texto, "bronce": tema.detalle}.get(medalla, tema.borde)
    pygame.draw.rect(pantalla, tema.borde, (cx - px(26), cy - px(150), px(52), px(70)))   # la cinta
    for k in range(6):   # disco escalonado, de pixel
        ancho = px(150) - abs(k - 2.5) * px(24)
        pygame.draw.rect(pantalla, color, (cx - ancho // 2, cy - px(72) + k * px(24), ancho, px(24)))
    num = fuentes.enorme.render(str(total), True, tema.fondo)
    pantalla.blit(num, num.get_rect(center=(cx, cy)))
    estrellas = ESTRELLAS.get(medalla, 0)
    for k in range(3):   # 3 oro, 2 plata, 1 bronce; las que faltan, en contorno
        c = (cx + (k - 1) * px(54), cy + px(118))
        _estrella(pantalla, tema.acento if k < estrellas else tema.borde, c, px(20))
    nombre = {"oro": "Medalla de oro", "plata": "Medalla de plata", "bronce": "Medalla de bronce"}.get(
        medalla, "Sin medalla: la ciudad necesita que verifiques mas")
    img = fuentes.normal.render(recortar(nombre, fuentes.normal, px(360)), True, tema.texto)
    pantalla.blit(img, img.get_rect(midtop=(cx, cy + px(150))))
    x, largo = CAJA.x + px(430), CAJA.right - px(40) - (CAJA.x + px(430))
    pantalla.blit(fuentes.normal.render("De donde salieron tus puntos (de 100)", True, tema.acento), (x, CAJA.y + px(40)))
    for k, (que, puntos, de) in enumerate(desglose):
        y = CAJA.y + px(84) + k * px(62)
        pantalla.blit(fuentes.normal.render(que, True, tema.texto), (x, y))
        valor = fuentes.normal.render(f"{puntos} de {de}", True, tema.texto)
        pantalla.blit(valor, valor.get_rect(topright=(x + largo, y)))
        barra = pygame.Rect(x, y + px(30), largo, px(18))
        pygame.draw.rect(pantalla, tema.fondo, barra)
        pygame.draw.rect(pantalla, tema.bueno if puntos * 2 >= de else tema.malo,
                         (barra.x, barra.y, round(barra.w * puntos / de), barra.h))
        pygame.draw.rect(pantalla, tema.borde, barra, px(2))
    y = CAJA.y + px(84) + len(desglose) * px(62) + px(8)   # la tabla de los mejores y las iniciales de quien jugo
    pantalla.blit(fuentes.normal.render("Mejores puntajes", True, tema.acento), (x, y))
    mejores = "   ".join(f"{k + 1}. {d['nombre']} {d['puntos']}" for k, d in enumerate((tabla or [])[:5]))
    pantalla.blit(fuentes.chica.render(recortar(mejores or "Todavia nadie: se el primero.", fuentes.chica, largo), True,
                                       tema.texto), (x, y + px(28)))
    if iniciales is None:
        pide = "Puntaje guardado."
    else:
        pide = f"Tus iniciales: {iniciales}{'_' * (3 - len(iniciales))}   (letras y Enter para guardarlo)"
    pantalla.blit(fuentes.chica.render(pide, True, tema.bueno if iniciales is None else tema.texto), (x, y + px(52)))
    _pie(pantalla, fuentes, tema, i, paginas)

