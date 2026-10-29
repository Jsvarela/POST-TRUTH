"""Multijugador (R12): pantalla para conectar (nombre, IP y puerto) y sala de espera (cada uno elige un rol distinto;
el anfitrion, el primero en llegar, inicia). Al llegar `inicio` la partida pasa a ser una SesionEnRed."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import Role
from post_truth.models.personaje import Genero
from post_truth.red.conexion import ConexionRed
from post_truth.red.sesion_red import SesionEnRed
from post_truth.views.componentes import Boton
from post_truth.views.red_view import (dibujar_conectar, dibujar_sala, rect_accion, rect_boton_conectar, rect_campo,
                                       rect_rol)

PUERTO = 5050
LARGO = {0: 16, 1: 40, 2: 5}   # nombre, IP, puerto
MOTIVOS = {"rol_tomado": "Ese rol ya lo eligio otro jugador.", "faltan_jugadores": "Hacen falta de 2 a 4 jugadores.",
           "faltan_roles": "Todos tienen que elegir un rol.", "solo_el_anfitrion": "Solo el anfitrion inicia.",
           "sala_llena": "La sala ya tiene 4 jugadores.", "partida_en_curso": "La partida ya empezo."}
ATAJOS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]


class ConectarState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.valores = ["Jugador", "127.0.0.1", str(PUERTO)]
        self.foco, self.t = 0, 0.0
        self.aviso: tuple[str, str] | None = None   # lo deja la sala si la conexion fallo
        self.boton = Boton(rect_boton_conectar(), "Conectar (Enter)", self.conectar)

    def al_entrar(self) -> None:
        self.t = 0.0

    def conectar(self) -> None:
        nombre, host, puerto = (v.strip() for v in self.valores)
        if not host or not puerto.isdigit() or not 0 < int(puerto) < 65536:
            self.aviso = ("Revisa la IP y el puerto (un numero de 1 a 65535).", "malo")
            return
        self.app.red = ConexionRed(host, int(puerto))
        self.app.red.enviar({"tipo": "unirse", "nombre": nombre or "Jugador"})   # sale apenas conecte
        self.aviso = None
        self.app.estados.cambiar("sala")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.boton.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.foco = next((i for i in range(3) if rect_campo(i).collidepoint(event.pos)), self.foco)
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.estados.cambiar("menu")
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.conectar()
        elif event.key in (pygame.K_TAB, pygame.K_DOWN, pygame.K_UP):
            self.foco = (self.foco + (-1 if event.key == pygame.K_UP else 1)) % 3
        elif event.key == pygame.K_BACKSPACE:
            self.valores[self.foco] = self.valores[self.foco][:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.valores[self.foco]) < LARGO[self.foco]:
            if self.foco != 2 or event.unicode.isdigit():
                self.valores[self.foco] += event.unicode

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, pantalla: pygame.Surface) -> None:
        campos = list(zip(("Tu nombre", "IP del servidor", "Puerto"), self.valores))
        dibujar_conectar(pantalla, self.app.fuentes, self.app.temas.actual, campos, self.foco, self.aviso, self.boton,
                         self.t)


class SalaState(BaseState):
    def al_entrar(self) -> None:
        self.t = 0.0
        self.jugadores: list[dict] = []
        self.yo: int | None = None
        self.genero = Genero.MUJER
        self.aviso: tuple[str, str] | None = ("Conectando...", "info")
        self._construir()

    @property
    def red(self) -> ConexionRed:
        return self.app.red

    @property
    def mio(self) -> dict | None:
        return self.jugadores[self.yo] if self.yo is not None and self.yo < len(self.jugadores) else None

    @property
    def soy_anfitrion(self) -> bool:
        return self.yo == 0

    def _construir(self) -> None:
        tomados = {j["rol"]: j["nombre"] for i, j in enumerate(self.jugadores) if j["rol"] and i != self.yo}
        mio = self.mio["rol"] if self.mio else None
        self.botones = []
        for i, rol in enumerate(Role):
            texto = f"{i + 1}. {rol.value}" + (f" ({tomados[rol.name]})" if rol.name in tomados else
                                                 " (tu)" if rol.name == mio else "")
            b = Boton(rect_rol(i), texto, lambda r=rol: self._elegir(r), atajo=ATAJOS[i])
            b.habilitado = rol.name not in tomados
            b.foco = rol.name == mio
            self.botones.append(b)
        self.botones.append(Boton(rect_accion(0), f"G. Personaje: {self.genero.value}", self._cambiar_genero,
                                  atajo=pygame.K_g))
        iniciar = Boton(rect_accion(1), "Iniciar partida (Enter)", self._iniciar, atajo=pygame.K_RETURN)
        iniciar.habilitado = (self.soy_anfitrion and 2 <= len(self.jugadores) <= 4
                              and all(j["rol"] for j in self.jugadores))
        self.botones += [iniciar, Boton(rect_accion(2), "Salir (ESC)", self._salir, atajo=pygame.K_ESCAPE)]

    def _elegir(self, rol: Role) -> None:
        self.red.enviar({"tipo": "elegir_rol", "rol": rol.name, "genero": self.genero.name})

    def _cambiar_genero(self) -> None:
        self.genero = Genero.HOMBRE if self.genero is Genero.MUJER else Genero.MUJER
        if self.mio and self.mio["rol"]:
            self._elegir(Role[self.mio["rol"]])
        self._construir()

    def _iniciar(self) -> None:
        self.red.enviar({"tipo": "iniciar"})

    def _salir(self) -> None:
        self.red.cerrar()
        self.app.red = None
        self.app.estados.cambiar("conectar")

    def handle_event(self, event: pygame.event.Event) -> None:
        for b in self.botones:
            if b.handle_event(event):
                return

    def update(self, dt: float) -> None:
        self.t += dt
        red = self.red
        if red is None:
            return
        for m in red.recibir():
            if m["tipo"] == "bienvenida":
                self.aviso = ("Conectado. Elige tu rol.", "bueno")
            elif m["tipo"] == "sala":
                self.jugadores, self.yo = m["jugadores"], m.get("yo")
                listos = sum(1 for j in self.jugadores if j["rol"])
                self.aviso = (f"{len(self.jugadores)} conectados, {listos} con rol. " +
                              ("Inicia cuando esten todos." if self.soy_anfitrion else "Espera al anfitrion."), "info")
            elif m["tipo"] == "error":
                self.aviso = (MOTIVOS.get(m["motivo"], m["motivo"]), "malo")
            elif m["tipo"] == "inicio":
                self._empezar(m)
                return
        if red.cerrada:
            self.app.red = None
            motivo = red.motivo or "se perdio la conexion"
            self.app.estados.estado("conectar").aviso = (motivo[0].upper() + motivo[1:], "malo")
            self.app.estados.cambiar("conectar")
            return
        self._construir()

    def _empezar(self, mensaje: dict) -> None:
        s = SesionEnRed.desde_inicio(mensaje, self.red)
        s.nombres = {sj.id: j["nombre"] for sj, j in zip(s.jugadores, self.jugadores)}   # mismo orden que la sala
        self.app.partida = s
        self.app.personaje = s.jugador_actual.personaje
        self.app.personajes = [j.personaje for j in s.jugadores]
        self.app.estados.estado("mundo")._dia = -1   # amanece en la Plaza aunque una partida anterior quedara a medias
        self.app.estados.cambiar("mundo", fundido=True)

    def filas(self) -> list[tuple[str, str, str]]:
        filas = []
        for i, j in enumerate(self.jugadores):
            rol = Role[j["rol"]].value if j["rol"] else "sin rol"
            extra = " - anfitrion" if j["anfitrion"] else ""
            filas.append((f"{j['nombre']}{' (tu)' if i == self.yo else ''}", f"{rol}{extra}",
                          "bueno" if j["rol"] else "info"))
        return filas

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_sala(pantalla, self.app.fuentes, self.app.temas.actual, self.filas(), self.botones, self.aviso, self.t)
