"""Vista animada de la propagacion de una noticia por el grafo social.

Solo LEE el grafo y el resultado de la simulacion (que ya se calculo en el modelo): aqui
unicamente se decide como dibujarlos y en que momento aparece cada ola. El tiempo avanza
con `dt` (nunca con sleep), asi el loop sigue a 60 FPS y el jugador puede saltar la animacion.

Colores (todos del tema, regla de accesibilidad):
    noticia falsa -> tema.malo        noticia verificada -> tema.bueno
    aro del nodo -> color del rol     conexion cortada   -> tema.acento
Ademas del color, cada nodo lleva la sigla de su rol, las conexiones debilitadas se ven mas
finas y las cortadas llevan una X, para que nada dependa solo del tono (daltonismo).
"""
import math

import pygame

from post_truth.config import px

from post_truth.models import Role
from post_truth.structures.grafo_social import GrafoSocial, ResultadoPropagacion
from post_truth.structures.propagacion import COMPARTIR, REPORTAR, SimulacionDecision
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import Tema

DURACION_OLA = 1.0   # segundos que tarda en viajar una ola
ENTRADA = 0.8        # pausa inicial: se ve el origen (y las conexiones cortadas) antes de salir
SALIDA = 0.8         # pausa final con el resultado completo
RADIO = px(15)
_ROLES = list(Role)
SIGLAS = {Role.CITIZEN: "Ci", Role.JOURNALIST: "Pe", Role.INFLUENCER: "In", Role.CANDIDATE: "Ca"}

Punto = tuple[float, float]


class AnimacionPropagacion:
    def __init__(self, grafo: GrafoSocial, simulacion: SimulacionDecision) -> None:
        self.grafo = grafo
        self.sim = simulacion
        self.t = 0.0

    # --- tiempo --------------------------------------------------------------------------
    @property
    def resultado(self) -> ResultadoPropagacion:
        return self.sim.resultado

    @property
    def duracion(self) -> float:
        # Con 0 olas (p. ej. Reportar) igual se muestra 1 ola de pausa para ver el corte.
        return ENTRADA + max(1, self.resultado.n_olas) * DURACION_OLA + SALIDA

    @property
    def terminada(self) -> bool:
        return self.t >= self.duracion

    def update(self, dt: float) -> None:
        self.t = min(self.duracion, self.t + dt)

    def saltar(self) -> None:
        self.t = self.duracion

    def _olas_completas(self) -> int:
        """Cuantas olas ya llegaron a su destino en este instante."""
        k = int((self.t - ENTRADA) // DURACION_OLA) if self.t >= ENTRADA else 0
        return min(max(k, 0), self.resultado.n_olas)

    def _ola_en_viaje(self) -> tuple[int, float] | None:
        """(numero de ola, progreso 0..1) de la ola que esta viajando ahora, o None."""
        k = self._olas_completas() + 1
        if self.t < ENTRADA or k > self.resultado.n_olas:
            return None
        return k, (self.t - ENTRADA - (k - 1) * DURACION_OLA) / DURACION_OLA

    def _alcanzados_visibles(self) -> list[str]:
        return [c for ola in self.resultado.olas[1:self._olas_completas() + 1] for c in ola]

    # --- texto narrado en la caja de dialogo --------------------------------------------
    def narracion(self) -> str:
        r, sim, g = self.resultado, self.sim, self.grafo
        nombre = lambda id: g.vertice(id).nombre  # noqa: E731
        if self.terminada:
            if r.alcanzados == 0:
                return "La noticia no logra salir de su origen."
            return (f"Llego a {r.alcanzados} de {r.poblacion} personas en {r.n_olas} olas. "
                    f"Tiempo estimado: {r.tiempo_mitad:.1f} h para la mitad, {r.tiempo_total:.1f} h en total.")
        en_viaje = self._ola_en_viaje()
        if en_viaje is None and self.t < ENTRADA:
            if sim.tipo == COMPARTIR:
                return "Compartes la publicacion. Mira como viaja por Civitas."
            if sim.tipo == REPORTAR:
                return f"Reportas la cuenta de {nombre(sim.autor)}: se cortan sus conexiones."
            if sim.aristas_debilitadas:
                return f"Verificas la noticia: la difusion de {nombre(sim.autor)} y su entorno se frena."
            return f"Verificas: la noticia es cierta y se difunde con normalidad desde {nombre(sim.autor)}."
        k = en_viaje[0] if en_viaje else self.resultado.n_olas
        if k == 0:
            return "La noticia no sale de su origen."
        nuevos = [nombre(c) for c in r.olas[k]]
        detalle = f" ({', '.join(nuevos)})" if len(nuevos) <= 3 else ""
        return f"Ola {k}: la reciben {len(nuevos)} persona(s){detalle}."

    # --- dibujo --------------------------------------------------------------------------
    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect) -> None:
        r = self.resultado
        color_noticia = tema.malo if r.es_falsa else tema.bueno
        pygame.draw.rect(pantalla, tema.panel, rect, border_radius=px(14))
        pygame.draw.rect(pantalla, tema.borde, rect, width=px(2), border_radius=px(14))
        area = pygame.Rect(rect.x + px(40), rect.y + px(58), rect.width - px(80), rect.height - px(140))
        pos = {c.id: (area.x + c.pos[0] * area.width, area.y + c.pos[1] * area.height)
               for c in self.grafo.vertices()}

        completas = self._olas_completas()
        recibidos = {r.origen} | set(self._alcanzados_visibles())
        usadas = {(r.padres[c], c) for c in recibidos if c in r.padres}  # aristas del arbol BFS ya recorridas

        # 1) conexiones existentes (grosor = peso: una conexion debilitada se ve mas fina)
        for a in self.grafo.aristas():
            ini, fin = _extremos(pos[a.origen], pos[a.destino])
            usada = (a.origen, a.destino) in usadas
            pygame.draw.line(pantalla, color_noticia if usada else tema.borde, ini, fin,
                             px(1) + round(px(3) * a.peso) + (px(1) if usada else 0))
            _flecha(pantalla, color_noticia if usada else tema.borde, ini, fin)
        # 2) conexiones cortadas por un Reportar: punteadas, con X
        if self.t > ENTRADA * 0.4:
            for o, d in self.sim.aristas_cortadas:
                ini, fin = _extremos(pos[o], pos[d])
                _punteada(pantalla, tema.acento, ini, fin)
                _equis(pantalla, tema.acento, ((ini[0] + fin[0]) / 2, (ini[1] + fin[1]) / 2))
        # 3) la ola en viaje: el tramo ya recorrido y un punto que avanza por cada arista
        viaje = self._ola_en_viaje()
        if viaje:
            k, p = viaje
            for destino in r.olas[k]:
                ini, fin = _extremos(pos[r.padres[destino]], pos[destino])
                punta = (ini[0] + (fin[0] - ini[0]) * p, ini[1] + (fin[1] - ini[1]) * p)
                pygame.draw.line(pantalla, color_noticia, ini, punta, px(4))
                pygame.draw.circle(pantalla, color_noticia, (round(punta[0]), round(punta[1])), px(6))
                pygame.draw.circle(pantalla, tema.texto, (round(punta[0]), round(punta[1])), px(6), 1)
        # 4) nodos
        frenados = {c for c in r.frenados if c in recibidos}
        for c in self.grafo.vertices():
            self._nodo(pantalla, fuentes, tema, c.id, pos[c.id], c.nombre.split()[0], c.rol,
                       recibido=c.id in recibidos, color=color_noticia,
                       es_origen=c.id == r.origen, frenado=c.id in frenados)
        # 5) contadores y leyenda
        vistos = len(recibidos) - 1
        texto = f"Ola {completas} de {r.n_olas}   |   {vistos} de {r.poblacion} personas la han visto"
        pantalla.blit(fuentes.normal.render(texto, True, tema.texto), (rect.x + px(18), rect.y + px(14)))
        _leyenda(pantalla, fuentes, tema, rect, color_noticia, r.es_falsa)

    def _nodo(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, id: str, pos: Punto,
              nombre: str, rol: Role, recibido: bool, color: tuple[int, int, int], es_origen: bool,
              frenado: bool) -> None:
        centro = (round(pos[0]), round(pos[1]))
        if es_origen:  # aro pulsante: de aqui sale la noticia
            pulso = px(4) + round(px(2) * math.sin(self.t * 6))
            pygame.draw.circle(pantalla, tema.acento, centro, RADIO + pulso, px(2))
        pygame.draw.circle(pantalla, color if recibido else tema.fondo, centro, RADIO)
        pygame.draw.circle(pantalla, tema.rol[_ROLES.index(rol)], centro, RADIO, px(3))
        sigla = fuentes.chica.render(SIGLAS[rol], True, tema.fondo if recibido else tema.texto)
        pantalla.blit(sigla, sigla.get_rect(center=centro))
        if frenado:  # recibio la noticia pero no la reenvia (periodista ante una falsa)
            _equis(pantalla, tema.texto, (centro[0] + RADIO - px(2), centro[1] - RADIO + px(2)), px(5))
        etiqueta = fuentes.chica.render(nombre, True, tema.texto)
        pantalla.blit(etiqueta, etiqueta.get_rect(midtop=(centro[0], centro[1] + RADIO + px(3))))


def _extremos(a: Punto, b: Punto) -> tuple[Punto, Punto]:
    """Segmento a->b acortado para no tapar los nodos y desplazado a un lado, de modo que
    las dos direcciones de una amistad mutua (a->b y b->a) no se dibujen encima una de otra."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    ox, oy = -uy * px(4), ux * px(4)
    return ((a[0] + ux * RADIO + ox, a[1] + uy * RADIO + oy),
            (b[0] - ux * (RADIO + px(1)) + ox, b[1] - uy * (RADIO + px(1)) + oy))


def _flecha(pantalla: pygame.Surface, color: tuple[int, int, int], ini: Punto, fin: Punto) -> None:
    dx, dy = fin[0] - ini[0], fin[1] - ini[1]
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    base = (fin[0] - ux * px(8), fin[1] - uy * px(8))
    pygame.draw.polygon(pantalla, color, [fin, (base[0] - uy * px(4), base[1] + ux * px(4)),
                                          (base[0] + uy * px(4), base[1] - ux * px(4))])


def _punteada(pantalla: pygame.Surface, color: tuple[int, int, int], ini: Punto, fin: Punto) -> None:
    largo = math.hypot(fin[0] - ini[0], fin[1] - ini[1]) or 1.0
    pasos = max(1, int(largo // px(8)))
    for i in range(0, pasos, 2):
        a, b = i / pasos, min(1.0, (i + 1) / pasos)
        pygame.draw.line(pantalla, color, (ini[0] + (fin[0] - ini[0]) * a, ini[1] + (fin[1] - ini[1]) * a),
                         (ini[0] + (fin[0] - ini[0]) * b, ini[1] + (fin[1] - ini[1]) * b), px(3))


def _equis(pantalla: pygame.Surface, color: tuple[int, int, int], centro: Punto, r: int | None = None) -> None:
    r = px(7) if r is None else r
    x, y = centro
    pygame.draw.line(pantalla, color, (x - r, y - r), (x + r, y + r), px(3))
    pygame.draw.line(pantalla, color, (x - r, y + r), (x + r, y - r), px(3))


def _leyenda(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
             color: tuple[int, int, int], es_falsa: bool) -> None:
    y = rect.bottom - px(52)
    paso = fuentes.chica.get_linesize() + px(4)
    pygame.draw.circle(pantalla, color, (rect.x + px(26), y + px(10)), px(8))
    etiqueta = "Noticia falsa" if es_falsa else "Noticia verificada"
    pantalla.blit(fuentes.chica.render(etiqueta, True, tema.texto), (rect.x + px(42), y))
    pantalla.blit(fuentes.chica.render("X: aqui la noticia se frena", True, tema.texto), (rect.x + px(220), y))
    pantalla.blit(fuentes.chica.render("Ci ciudadano   Pe periodista   In influencer   Ca candidato",
                                       True, tema.texto), (rect.x + px(18), y + paso))
