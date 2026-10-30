"""Controlador del mundo caminable: la calle entre noticia y noticia."""
import math
import random

import pygame

from post_truth.config import px, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_MAPA, RUTA_MINIJUEGOS
from post_truth.controllers import roles_teclas
from post_truth.controllers.base_state import BaseState
from post_truth.decision_tree import load_trees
from post_truth.models import Role
from post_truth.models import minijuego as mj
from post_truth.models import guia
from post_truth.models import transeuntes as tr
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models.animacion import AnimacionPersonaje
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import FIN, FIN_DIA, PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views import hud
from post_truth.views.hud import DatosHud
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.decorado import generar as generar_decorado
from post_truth.views.mundo_view import RECT_MINIMAPA, Camara, EstadoMundo, dibujar_mundo
from post_truth.views.roles_view import dibujar_habilidad, dibujar_menu_aliados

DIRECCIONES = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}
DURACION_AVISO = 4.0
PASOS = 0.35         # segundos entre paso y paso
RECT_HABILIDAD = pygame.Rect(RECT_MINIMAPA.x, RECT_MINIMAPA.y, px(220), px(48))   # donde va el minimapa en la pausa


def salud(c) -> float:
    """-1..1: lo bueno de la ciudad contra lo malo; 0 es la ciudad al empezar."""
    bueno = (c.verified_information + c.trust + c.coexistence + c.digital_wellbeing) / 4
    malo = (c.misinformation + c.conflicts) / 2
    return max(-1.0, min(1.0, (bueno - malo - 28.5) / 40))


class MundoState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rng = random.Random()
        self.mundo = MapaAbierto.cargar(RUTA_MAPA)
        self.presionadas: set[int] = set()
        self.aviso, self._t_aviso = "", 0.0
        self.guia = False
        self.animacion = AnimacionPersonaje()
        self.camara = Camara(self.mundo.jugador)
        self.decorado = generar_decorado(self.mundo)
        self.depuracion = False     # F3: zonas, colisiones y aristas
        self.t = 0.0
        self._dia = -1   # dia de campana que ya se preparo en el mundo
        self.anuncio: Anuncio | None = None   # grande, en el centro (el nuevo dia)
        self.toast: Anuncio | None = None     # corto, arriba
        self.pausa = False          # P: minimapa, indicadores y teclas con el mundo quieto (L2)
        self.paso_visto = ""        # el paso del dia que ya se aviso
        self.menu_aliados = False   # Y: pedir ayuda a los aliados
        self.otros: dict[str, tuple[tuple[float, float], AnimacionPersonaje]] = {}   # multijugador: los demas
        self.calle: dict[str, tuple[tuple[float, float], AnimacionPersonaje]] = {}   # transeuntes
        self.charlando: str | None = None   # transeunte con quien se habla mientras E sigue apretada
        self._t_pasos = 0.0

    @property
    def personaje(self) -> Personaje:
        return getattr(self.app, "personaje", None) or Personaje(Role.CITIZEN, Genero.MUJER)

    @property
    def sesion(self) -> PartidaSesion:
        return self.app.partida

    @property
    def jugador_id(self) -> str:
        return self.sesion.jugador_actual.id

    def al_entrar(self) -> None:
        if self.app.partida is None:
            self.app.partida = PartidaSesion.nueva_campana(
                getattr(self.app, "personajes", None) or [self.personaje], load_trees(RUTA_EVENTOS), GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng, extendido=self.app.tiempo_extendido,
                minijuegos=mj.cargar_lugares(RUTA_MINIJUEGOS))
            self._dia = -1
        if self.sesion.campana.dia != self._dia:   # amanece: de vuelta en la Plaza
            self._dia = self.sesion.campana.dia
            self.mundo.ir_a(self.sesion.mapa.zona_inicial)
            self._situar()
            self.guia = False
            self.animacion = AnimacionPersonaje()
            c = self.sesion.campana
            f = self.sesion.fase_actual
            texto = f"{f.nombre}: {f.descripcion}" if f else "Amanece en Ciudad Nova." 
            self.anuncio = Anuncio(f"Dia {c.dia + 1} de {len(c.dias)}", texto, "dia", duracion=2.4)
        self.mundo.sincronizar(self.sesion.mapa)   # el grafo manda: aristas que faltan = barreras
        self.camara.saltar(self.mundo.jugador)
        self.presionadas.clear()
        self.aviso, self._t_aviso = "", 0.0

    def _avisar(self, texto: str, titulo: str = "", tipo: str = "info") -> None:
        """El texto queda en la franja; con `titulo` ademas baja un toast animado."""
        self.aviso, self._t_aviso = texto, DURACION_AVISO
        if titulo:
            self.toast = Anuncio(titulo, texto, tipo, grande=False, duracion=DURACION_AVISO)

    def _situar(self) -> None:
        self.sesion.situar(self.jugador_id, self.mundo.jugador, self.zona_aqui())

    def zona_aqui(self) -> str | None:
        """La zona que pisa el jugador: E funciona en cualquier punto dentro de ella."""
        return self.mundo.zona_en(self.mundo.jugador)

    def etiqueta_calle(self) -> str:
        t = self.sesion.transeunte_cerca(self.jugador_id)
        if t is None:
            return ""
        if t.testigo or t.dice:
            return f"Manten E: escuchar a {t.nombre}"
        return f"Manten E: convencer a {t.nombre} (rumor)"

    def accion_disponible(self) -> tuple[str, str] | None:
        """(zona, "entrar") si el jugador esta dentro de un lugar: E entra siempre y adentro se decide."""
        zona = self.zona_aqui()
        return (zona, "entrar") if zona is not None else None

    def etiqueta(self, que: str, zona: str) -> str:
        return f"Entrar a {self.mundo.zonas[zona].nombre}"

    def _usar(self) -> None:
        if self.zona_aqui() is not None:
            self.presionadas.clear()
            self.app.estados.cambiar("lugar", fundido=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.pausa:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_p, pygame.K_ESCAPE):
                self.pausa = False
            return
        if event.type == pygame.KEYDOWN:
            era, self.menu_aliados, aviso = roles_teclas.tecla(self.sesion, self.menu_aliados, event.key)
            if aviso is not None:
                self._avisar(aviso[1], aviso[0], aviso[2])
            if era:
                return
            if event.key == pygame.K_ESCAPE:
                self.app.salir_de_red()
                self.app.partida = None
                self.app.estados.cambiar("menu")
            elif event.key in DIRECCIONES:
                self.presionadas.add(event.key)
            elif event.key == pygame.K_e:
                t = self.sesion.transeunte_cerca(self.jugador_id)
                if t is not None:              # hablar con alguien de la calle tiene prioridad sobre entrar
                    self.charlando = t.id
                else:
                    self._usar()
            elif event.key == pygame.K_g:
                self.guia = not self.guia
            elif event.key == pygame.K_F3:
                self.depuracion = not self.depuracion
            elif event.key == pygame.K_p:
                self.presionadas.clear()
                self.pausa = True
        elif event.type == pygame.KEYUP:
            self.presionadas.discard(event.key)
            if event.key == pygame.K_e and self.charlando is not None:
                self.charlando = None
                self._fin_charla(self.sesion.soltar(self.jugador_id))

    def update(self, dt: float) -> None:
        if self.pausa:
            return
        for anuncio in ("anuncio", "toast"):
            a = getattr(self, anuncio)
            if a is not None:
                a.avanzar(dt)
                if a.terminado:
                    setattr(self, anuncio, None)
        dx = sum(DIRECCIONES[k][0] for k in self.presionadas)
        dy = sum(DIRECCIONES[k][1] for k in self.presionadas)
        self.mundo.sincronizar(self.sesion.mapa)   # una protesta puede cerrar una frontera a mitad del dia
        self._red(dt)
        antes, zona_antes = self.mundo.jugador, self.zona_aqui()
        self.mundo.mover(dx, dy, dt)
        zona = self.zona_aqui()
        if zona is not None and zona != zona_antes:
            self._avisar(f"Entraste a {self.mundo.zonas[zona].nombre}.")
        self._situar()
        self.animacion.actualizar(dx, dy, math.dist(antes, self.mundo.jugador), dt)
        self._pasos(math.dist(antes, self.mundo.jugador), dt)
        self._calle(dt)
        self.camara.seguir(self.mundo.jugador, dt)
        self.t += dt
        s = self.sesion
        vencida = s.transcurrir(dt)
        if s.novedad == "mapa":                           # una protesta, una crisis de zona o un aislamiento
            s.novedad = ""
            n = s.notificaciones[-1]
            self._avisar(n["texto"], n["titulo"], n["tipo"])
        if s.novedad == "crisis":                         # la consecuencia abre el telefono (que la anuncia)
            self.presionadas.clear()
            self.anuncio = None
            self.app.estados.cambiar("telefono")
        elif vencida is not None or (s.pendiente is not None and s.pendiente.jugador == self.jugador_id):
            # vencio el reloj (aqui o mientras se jugaba un minijuego): se ve adentro lo que paso
            self.presionadas.clear()
            self.app.estados.cambiar("escena", fundido=True)
        elif s.fase in (FIN_DIA, FIN):                    # se acabo el dia en la calle
            self.presionadas.clear()
            self.app.estados.cambiar("resumen", fundido=True)
        self._t_aviso = max(0.0, self._t_aviso - dt)
        if self._t_aviso == 0:
            self.aviso = ""
        if s.director is not None and s.director.nombre != self.paso_visto and self.app.estados.actual is self:
            self.paso_visto = s.director.nombre   # la historia presenta las herramientas del paso
            if (aviso := roles_teclas.aviso_paso(s)) is not None:
                self._avisar(aviso[1], aviso[0], aviso[2])
        self._guiar()

    def _guiar(self) -> None:
        """Mensajes guia de la primera vez, de a uno y sin tapar otro aviso (models/guia.py)."""
        if self.toast is not None or self.app.estados.actual is not self:
            return
        s = self.sesion
        cerca = s.transeunte_cerca(self.jugador_id)
        claves = ["inicio", "zona" if self.zona_aqui() else "", "protesta" if s.protestas else "",
                  ("testigo" if cerca.testigo else "transeunte") if cerca is not None else "",
                  "credibilidad" if s.jugador_actual.credibilidad < 40 else ""]
        for clave in filter(None, claves):
            m = guia.mensaje(clave, self.app.guias_vistas, self.app.guias)
            if m is not None:
                self.toast = Anuncio(m[0], m[1], "info", grande=False, duracion=DURACION_AVISO + 1)
                return

    def _calle(self, dt: float) -> None:
        """Anima a los transeuntes y avanza la charla mientras E siga apretada."""
        s = self.sesion
        if s.calle is None:
            return
        for t in s.calle.transeuntes:
            antes, anim = self.calle.get(t.id, (tuple(t.pos), AnimacionPersonaje()))
            ahora = tuple(t.pos)
            anim.actualizar(ahora[0] - antes[0], ahora[1] - antes[1], math.dist(antes, ahora), dt)
            self.calle[t.id] = (ahora, anim)
        if self.charlando is not None:
            r = s.hablar(self.jugador_id, self.charlando, dt)
            if r or s.charla is None:          # termino, o se alejo y se corto
                self.charlando = None
                self._fin_charla(r or "lejos")

    def _pasos(self, movido: float, dt: float) -> None:
        """Un paso cada PASOS segundos mientras se camina (aviso visual: la animacion de caminar)."""
        if movido <= 0:
            self._t_pasos = 0.0
            return
        self._t_pasos -= dt
        if self._t_pasos <= 0:
            sonido.tocar("pasos")
            self._t_pasos = PASOS

    def _fin_charla(self, como: str) -> None:
        if como in ("convencido", "testigo", "enojado", "escuchado"):
            sonido.tocar("error" if como == "enojado" else "acierto")
        if como == "convencido":
            self._avisar("Ya no va a regar ese rumor.", "Lo convenciste", "bueno")
        elif como in ("testigo", "escuchado"):
            n = self.sesion.notificaciones[-1]
            self._avisar(n["texto"], n["titulo"], "bueno" if como == "testigo" else "info")
        elif como == "enojado":
            self._avisar("No quiso escucharte. Con evidencia o mas credibilidad te va mejor.", "Se enojo", "malo")
        elif como == "lejos":
            self._avisar("Se fue: hay que seguirle el paso mientras le hablas.")

    def vista_calle(self) -> tuple[tuple, tuple | None]:
        """(transeuntes para dibujar, charla en curso) con lo que la vista necesita."""
        s = self.sesion
        if s.calle is None:
            return (), None
        salida = []
        for t in s.calle.transeuntes:
            pos, anim = self.calle.get(t.id, (tuple(t.pos), AnimacionPersonaje()))
            marca = "enojado" if t.enojado > 0 else "rumor" if t.rumor else "testigo" if t.testigo or t.dice else ""
            if t.testigo and s.jugador_actual.investigacion.esta_descubierta(t.testigo):
                marca = ""
            genero = Genero.MUJER if t.nombre.split()[0].endswith("a") else Genero.HOMBRE
            salida.append((t.nombre, Personaje(Role[t.rol], genero, sum(map(ord, t.id)) % 2), pos, anim.nombre,
                           anim.cuadro, marca))
        c = s.charla
        if c is None or c["jugador"] != self.jugador_id or s.calle.buscar(c["id"]) is None:
            return tuple(salida), None
        t = s.calle.buscar(c["id"])
        if c["p"] is None:
            que = "te cuenta lo que vio..." if t.testigo else "quiere contarte algo..."
            return tuple(salida), (tuple(t.pos), min(1.0, c["t"] / tr.datos()["escuchar"]), f"{t.nombre} {que}", "")
        p = c["p"]
        return tuple(salida), (tuple(t.pos), (len(p.camino) + p.progreso) / 3,
                               f"{t.nombre}: {p.nodo.texto if p.nodo else ''}", f"Tu: {p.opcion.texto if p.opcion else ''}")

    def _red(self, dt: float) -> None:
        """Multijugador: el servidor corrige una posicion invalida, y se anima a los demas entre fotos."""
        s = self.sesion
        if not getattr(s, "en_red", False):
            return
        if s.correccion is not None:
            self.mundo.jugador, s.correccion = s.correccion, None
            self._avisar("Por ahi no se puede pasar.", "No se puede pasar", "malo")
        if s.acciones and self.toast is None:
            titulo, texto, tipo = s.acciones.pop(0)   # lo que hicieron los demas (o un rechazo del servidor)
            self._avisar(texto, titulo, tipo)
        for jid, pos, direccion, caminando in s.remotos_en():
            antes, anim = self.otros.get(jid, (pos, AnimacionPersonaje()))
            anim.direccion = direccion
            anim.actualizar(0, 0, math.dist(antes, pos) if caminando else 0.0, dt)
            self.otros[jid] = (pos, anim)

    def vista_otros(self) -> tuple:
        s = self.sesion
        if not getattr(s, "en_red", False):
            return ()
        return tuple((s.nombre(jid) + ("" if s.conectados.get(jid, True) else " (sin conexion)"),
                      s.jugador(jid).personaje, pos, anim.nombre, anim.cuadro, s.conectados.get(jid, True))
                     for jid, (pos, anim) in self.otros.items())

    def estado_vista(self) -> EstadoMundo:
        s = self.sesion
        calle = self.vista_calle()
        d = s.director
        destino = d.destino if d is not None else s.zona_noticia   # L2: la guia apunta solo al objetivo del paso
        zonas, puntos = (self.mundo.ruta_puntos(s.mapa, self.mundo.ultima_zona, destino) if self.guia and destino
                         else ((), []))
        inv = s.jugador_actual.investigacion
        investigando = d is None or d.nombre == "noticia"
        return EstadoMundo(
            noticia=destino or "", evidencias=inv.lugares_pendientes() - {destino} if investigando else frozenset(),
            flecha=self.mundo.zonas[destino].centro if destino in self.mundo.zonas and d is not None else None,
            pausa=self.pausa,
            accion=self.accion_disponible(),
            indicadores=s.ciudad.as_display_rows(), guia=zonas, guia_puntos=tuple(puntos), aviso=self.aviso,
            crisis=s.director is not None and s.director.nombre == "consecuencia", depuracion=self.depuracion,
            abiertas=frozenset(z.id for z in s.mapa.zonas()), zonas_crisis=frozenset(s.zonas_crisis),
            aisladas=frozenset(s.aisladas), noche=bool(s.fase_actual and s.fase_actual.variante == "noche"),
            salud=salud(s.ciudad),
            personaje=self.personaje, animacion=self.animacion, centro_camara=self.camara.centro,
            decorado=self.decorado, t=self.t,
            reloj=(s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None,
            dia=(s.campana.dia + 1, len(s.campana.dias)), fraccion_dia=s.campana.fraccion,
            credibilidad=s.jugador_actual.credibilidad, otros=self.vista_otros(),
            transeuntes=calle[0], charla=calle[1],
            texto_accion=self.etiqueta_calle() or (self.etiqueta(accion[1], accion[0]) if (accion := self.accion_disponible())
                                                   and accion[1] != "elegir" else ""))

    def datos_hud(self) -> DatosHud | None:
        s = self.sesion
        if s is None:
            return None
        if not self.pausa:   # L2: dia, objetivo y credibilidad; todo lo demas en la pausa o el cierre
            return hud.minimo(s, s.jugador_actual.credibilidad)
        f = s.fase_actual
        return DatosHud(s.ciudad.as_display_rows(), s.jugador_actual.credibilidad, "placa",
                        (s.campana.dia + 1, len(s.campana.dias)), f.nombre if f else "", s.campana.fraccion,
                        id(s.ciudad))

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        dibujar_mundo(pantalla, self.app.fuentes, tema, self.mundo, self.estado_vista())
        if (h := roles_teclas.habilidad(self.sesion)) is not None and not self.pausa:
            dibujar_habilidad(pantalla, self.app.fuentes, tema, RECT_HABILIDAD, h)
        if self.menu_aliados:
            dibujar_menu_aliados(pantalla, self.app.fuentes, tema, roles_teclas.filas_aliados(self.sesion))
        if self.app.estados.actual is not self:   # detras del telefono: sin anuncios encima
            return
        for a in (self.toast, self.anuncio):
            if a is not None:
                dibujar_anuncio(pantalla, self.app.fuentes, tema, a)
