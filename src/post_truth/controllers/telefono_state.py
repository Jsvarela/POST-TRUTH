"""Telefono Civitas: se abre solo en el paso de consecuencia (L1/L2) y dura lo que dura la defensa. Pestana Red =
"Frena el rumor": mueve el escudo (WASD, flechas o raton) para atajar los rumores que viajan por la red y lanza el
desmentido en onda con Espacio. Publicar aparece solo el dia que la historia lo pide."""
import pygame

from post_truth.controllers import roles_teclas
from post_truth.controllers.base_state import BaseState
from post_truth.controllers.mundo_state import RECT_HABILIDAD
from post_truth.models import guia, posts
from post_truth.sesion import FIN, FIN_DIA, RITMO_RUMOR_TELEFONO, RITMO_TELEFONO
from post_truth.views.hud import DatosHud
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.componentes import Modal
from post_truth.views.roles_view import dibujar_habilidad, dibujar_menu_aliados
from post_truth.views.telefono_view import (AREA_RED, ASPECTO, CERRAR, ONDA, PESTANAS, RADIO_ESCUDO,
                                            RECT_PUBLICAR, VistaPublicar, VistaTelefono, de_pantalla,
                                            dibujar_telefono, rect_fila, rect_pestana)

MOVER = {pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
         pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0)}
VELOCIDAD_ESCUDO = 0.9   # alto del area por segundo (tiempo real: el escudo no se frena con el mundo)
ALERTA = 3.0   # segundos que parpadea el aviso de "se volvio viral"
MOTIVOS = {"enfriando": "Aun se esta recargando.", "sin_rumor": "No hay un rumor corriendo ahora.",
           "en_curso": "Tu post anterior sigue circulando.",
           "contradice_verdad": "La red ya habla de algo cierto: no lo contradigas con algo falso.",
           "fuera_de_paso": "Ahora no: la historia te lo ofrecera en su momento."}


class TelefonoState(BaseState):
    def al_entrar(self) -> None:
        s = self.app.partida
        self.pestana, self.t, self.alerta = 0, 0.0, 0.0
        self.toast: Anuncio | None = None
        self.modal: Modal | None = None
        self.pulsos: dict[str, float] = {}
        self._previo: dict[str, str] = dict(s.en_vivo.estado) if s.en_vivo is not None else {}
        self.escudo = (0.5, 0.5)
        self.teclas: set[int] = set()
        self.ondas: list[list] = []   # [centro, edad]
        self.atajo = 0.0
        self.fila = 0
        self.menu_aliados = False
        self.paso_visto = ""
        self.eleccion = getattr(self, "eleccion", None) or {p: 0 for p in posts.PIEZAS}   # se recuerda lo armado
        m = guia.mensaje("telefono", self.app.guias_vistas, self.app.guias)
        if m is not None:
            self._avisar(m[0], m[1], "info")
        if s.novedad == "crisis":   # la crisis abre el telefono sola, con su reloj
            s.novedad = ""
            self.modal = Modal("Crisis viral!", f"\"{s.arbol.event.title}\" se esta regando en "
                               f"{s.zona_noticia.capitalize()}. Tienes {round(s.tiempo_restante or 0)} s: frenala "
                               "desde la red.", ("Defender la red",), "crisis")
            self.modal.cuenta = (s.tiempo_restante or 0.0, s.tiempo_viral_total)

    @property
    def en_pausa(self) -> bool:
        """El modal de la crisis detiene todo mientras se lee."""
        return self.modal is not None

    def _cerrar(self) -> None:
        self.app.estados.cambiar("mundo")

    def _avisar(self, titulo: str, texto: str, tipo: str) -> None:
        self.toast = Anuncio(titulo, texto, tipo, grande=False, duracion=2.2)

    @property
    def radio(self) -> float:
        return RADIO_ESCUDO * (1.4 if self.app.partida.campana.factor > 1 else 1.0)

    def lanzar_onda(self) -> None:
        r = self.app.partida.onda(self.escudo)
        if r.ok:
            self.ondas.append([self.escudo, 0.0])
        else:
            self._avisar("Desmentido", MOTIVOS.get(r.motivo, "No se pudo."), "info" if r.motivo == "sin_rumor" else "malo")

    def _opciones(self, pieza: str) -> list[dict]:
        return posts.reglas().opciones(pieza, self.app.partida.jugador_actual.rol.name)

    def post(self) -> posts.Post:
        return posts.Post(**{p: self._opciones(p)[self.eleccion[p] % len(self._opciones(p))]["id"]
                             for p in posts.PIEZAS})

    def _cambiar_pieza(self, paso: int) -> None:
        pieza = posts.PIEZAS[self.fila]
        self.eleccion[pieza] = (self.eleccion[pieza] + paso) % len(self._opciones(pieza))

    def publicar(self) -> None:
        ok, motivo, _ = self.app.partida.publicar(self.post())
        if ok:
            self._avisar("Publicado", "Mira en la pestana Red como viaja.", "bueno")
            self.pestana = 0
        else:
            self._avisar("No se pudo publicar", MOTIVOS.get(motivo, "No se pudo."), "malo")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            if self.modal.handle_event(event) is not None:
                self.modal = None
            return
        if event.type == pygame.KEYDOWN:
            era, self.menu_aliados, aviso = roles_teclas.tecla(self.app.partida, self.menu_aliados, event.key)
            if aviso is not None:
                self._avisar(*aviso)
            if era:
                return
            if event.key in (pygame.K_t, pygame.K_ESCAPE):
                self._cerrar()
            elif event.key == pygame.K_TAB:
                self.pestana = (self.pestana + 1) % self.pestanas
            elif self.pestana == 2:
                self._tecla_publicar(event.key)
            elif self.pestana == 0 and event.key in MOVER:
                self.teclas.add(event.key)
            elif self.pestana == 0 and event.key == pygame.K_SPACE:
                self.lanzar_onda()
        elif event.type == pygame.KEYUP:
            self.teclas.discard(event.key)
        elif event.type == pygame.MOUSEMOTION and self.pestana == 0 and AREA_RED.collidepoint(event.pos):
            self.escudo = de_pantalla(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._clic(event.pos)

    @property
    def pestanas(self) -> int:
        """Red y Notificaciones siempre; Publicar solo cuando la historia lo ofrece."""
        d = self.app.partida.director
        return len(PESTANAS) if d is None or d.ofrece("post") else len(PESTANAS) - 1

    def _tecla_publicar(self, key: int) -> None:
        if key in (pygame.K_UP, pygame.K_w):
            self.fila = (self.fila - 1) % len(posts.PIEZAS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.fila = (self.fila + 1) % len(posts.PIEZAS)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._cambiar_pieza(-1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._cambiar_pieza(1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.publicar()

    def _clic(self, punto: tuple[int, int]) -> None:
        if CERRAR.collidepoint(punto):
            self._cerrar()
            return
        for i in range(self.pestanas):
            if rect_pestana(i).collidepoint(punto):
                self.pestana = i
                return
        if self.pestana == 2:
            for i in range(len(posts.PIEZAS)):
                r = rect_fila(i)
                if r.collidepoint(punto):   # mitad izquierda: anterior; derecha: siguiente
                    self.fila = i
                    self._cambiar_pieza(-1 if punto[0] < r.centerx else 1)
                    return
            if RECT_PUBLICAR.collidepoint(punto):
                self.publicar()
            return
        if self.pestana == 0 and AREA_RED.collidepoint(punto):   # clic en la red: onda donde esta el escudo
            self.escudo = de_pantalla(punto)
            self.lanzar_onda()

    def update(self, dt: float) -> None:
        if self.toast is not None:
            self.toast.avanzar(dt)
            if self.toast.terminado:
                self.toast = None
        self.t += dt   # el telefono sube aunque la crisis tenga todo en pausa
        if self.modal is not None:
            self.modal.update(dt)
            return
        self.pulsos = {id: e + dt for id, e in self.pulsos.items() if e + dt < 1.0}
        self.ondas = [[c, e + dt] for c, e in self.ondas if e + dt < ONDA]
        dx = sum(MOVER[k][0] for k in self.teclas)
        dy = sum(MOVER[k][1] for k in self.teclas)
        if dx or dy:   # el escudo se mueve en tiempo real (el mundo va al 25%, el jugador no)
            x, y = self.escudo
            self.escudo = (min(1.0, max(0.0, x + dx * VELOCIDAD_ESCUDO * dt / ASPECTO)),
                           min(1.0, max(0.0, y + dy * VELOCIDAD_ESCUDO * dt)))
        v = self.app.partida.en_vivo
        self.atajo = max(0.0, self.atajo - dt)
        if self.app.partida.escudo(self.escudo, self.radio):
            self.atajo = 0.35   # destello del escudo: lo atajaste
            sonido.tocar("acierto")
        if v is not None:   # a quien le acaba de llegar algo: pulso
            for id, estado in v.estado.items():
                if estado != self._previo.get(id, estado):
                    self.pulsos[id] = 0.0
            self._previo = dict(v.estado)
        self.alerta = max(0.0, self.alerta - dt)
        s = self.app.partida
        if s.director is not None and s.director.nombre != self.paso_visto:
            self.paso_visto = s.director.nombre
            if (aviso := roles_teclas.aviso_paso(s)) is not None and self.toast is None:
                self._avisar(*aviso)
        if getattr(s, "en_red", False) and s.acciones and self.toast is None:   # lo que hacen los demas
            titulo, texto, tipo = s.acciones.pop(0)
            self._avisar(titulo, texto, tipo)
        vencida = s.transcurrir(dt * RITMO_TELEFONO)
        s.avanzar_rumor(dt * (RITMO_RUMOR_TELEFONO - RITMO_TELEFONO))   # transcurrir ya lo movio al 25%
        if s.novedad == "viral":
            s.novedad = ""
            self.alerta = ALERTA
            sonido.alerta()
            self._avisar("Se volvio viral!", "El rumor ya llega a mucha gente.", "malo")
        if self.pestana == 1:
            s.leidas = len(s.notificaciones)
        if vencida is not None:                 # se acabo el reloj de la crisis: se ve adentro lo que paso
            self.app.estados.cambiar("escena", fundido=True)
        elif s.fase in (FIN_DIA, FIN):
            self.app.estados.cambiar("resumen", fundido=True)
        elif s.novedad == "crisis":             # una crisis nueva mientras se mira la red
            self.al_entrar()

    def vista(self) -> VistaTelefono:
        s = self.app.partida
        post, reglas = self.post(), posts.reglas()
        filas = [(p, next(o["texto"] for o in self._opciones(p) if o["id"] == getattr(post, p))) for p in posts.PIEZAS]
        publicar = VistaPublicar(filas, self.fila, reglas.evaluar(post, s.jugador_actual.rol.name),
                                 s.enfriamiento_post, reglas.reglas["enfriamiento"], s.post is not None)
        return VistaTelefono(s.grafo, s.en_vivo, self.pestana, self.escudo, s.notificaciones, s.leidas,
                             (s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None,
                             s.campana.factor > 1, self.alerta, self.t, publicar, self.pulsos, s.campana.fraccion,
                             tuple((tuple(c), e) for c, e in self.ondas), self.atajo, self.pestanas)

    def datos_hud(self) -> DatosHud | None:
        return None   # el telefono tapa el centro: lleva su propia barra de estado y la cuenta de la crisis

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        self.app.estados.estado("mundo").draw(pantalla)   # la calle detras, quieta
        dibujar_telefono(pantalla, self.app.fuentes, tema, self.vista())
        if (h := roles_teclas.habilidad(self.app.partida)) is not None:
            dibujar_habilidad(pantalla, self.app.fuentes, tema, RECT_HABILIDAD, h)
        if self.menu_aliados:
            dibujar_menu_aliados(pantalla, self.app.fuentes, tema, roles_teclas.filas_aliados(self.app.partida))
        if self.toast is not None:
            dibujar_anuncio(pantalla, self.app.fuentes, tema, self.toast)
        if self.modal is not None:
            self.modal.draw(pantalla, self.app.fuentes, tema)
