"""Servidor del multijugador (R11): mantiene la PartidaSesion, corre la simulacion y valida cada accion.

Un solo hilo con `selectors` (biblioteca estandar): el bucle espera mensajes con un tiempo limite (nunca `sleep`),
avanza la simulacion con el dt real y manda una foto del estado unas 10 veces por segundo. El servidor es
AUTORITATIVO: solo el llama a transcurrir/aplicar/continuar, asi que la fase, el grafo de la ciudad (zonas
abiertas, fronteras cerradas, crisis) y el rumor en vivo solo cambian aqui. El movimiento es local en cada cliente;
el servidor solo valida las posiciones (no atravesar muros ni fronteras cerradas) para mostrarlas a los demas.

Uso:  python -m post_truth.red.servidor --puerto 5050
"""
from __future__ import annotations

import argparse
import math
import random
import secrets
import selectors
import socket
import time

from post_truth.config import (RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_MAPA,
                               RUTA_MINIJUEGOS)
from post_truth.decision_tree import load_trees
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models import Role
from post_truth.models import minijuego as mj
from post_truth.models import posts, roles
from post_truth.models.personaje import Genero, Personaje
from post_truth.red.protocolo import Lector, MensajeInvalido, empaquetar
from post_truth.sesion import CONSECUENCIA, DECIDIENDO, FIN, FIN_DIA, MAX_JUGADORES, PartidaSesion
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion_vivo import ASPECTO_RED, RADIO_ESCUDO

FOTO = 0.1               # segundos entre fotos del estado (10 por segundo)
MIN_JUGADORES = 2
GRACIA = 10.0            # segundos que se espera a un jugador desconectado en su turno antes de decidir por el
AUTO_CONTINUAR = 30.0    # segundos que se espera a que quien decidio cierre la animacion o las consecuencias
ESPERA_DIA = 15.0        # resumen del dia: se sigue cuando todos lo pasan o despues de esto
MAX_SALIDA = 1024 * 1024 # un cliente que no lee (mas de 1 MB pendiente) se desconecta
ESCUDO_VIGENTE = 0.5     # un escudo que no se actualiza en este tiempo deja de atajar
HOLGURA_VELOCIDAD = 1.6  # el cliente puede ir algo mas rapido que la velocidad (lag, sub-pasos)


class Rechazo(Exception):
    """Una accion que las reglas no permiten: se contesta con `error` y no cambia nada."""


class Conexion:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.lector = Lector()
        self.salida = bytearray()
        self.lugar: dict | None = None     # su entrada en la sala
        self.ack = 0                       # el ultimo "n" de sus acciones ya procesado (va en cada foto)


class Servidor:
    def __init__(self, host: str = "127.0.0.1", puerto: int = 0, semilla: int | None = None,
                 gracia: float = GRACIA, auto_continuar: float = AUTO_CONTINUAR, espera_dia: float = ESPERA_DIA,
                 acelerar: float = 1.0) -> None:
        self.selector = selectors.DefaultSelector()
        self.escucha = socket.create_server((host, puerto))
        self.escucha.setblocking(False)
        self.selector.register(self.escucha, selectors.EVENT_READ)
        self.conexiones: dict[socket.socket, Conexion] = {}
        self.sala: list[dict] = []          # {nombre, token, rol, genero, jugador, conexion}
        self.sesion: PartidaSesion | None = None
        self.mapa = MapaAbierto.cargar(RUTA_MAPA)   # para validar posiciones (sin ventana)
        self.rng = random.Random(semilla)
        self.gracia, self.auto_continuar, self.espera_dia = gracia, auto_continuar, espera_dia
        self.acelerar = acelerar            # pruebas: la simulacion corre mas rapido que el reloj
        self.posiciones: dict[str, dict] = {}   # jugador -> {pos, dir, t}
        self.escudos: dict[str, tuple[tuple[float, float], float]] = {}
        self.eventos: list[dict] = []       # lo que hicieron los jugadores y las novedades, numerado
        self.t = 0.0
        self._foto = 0.0
        self._espera = 0.0                  # tiempo esperando a un desconectado, en consecuencias o en el resumen
        self._listos: set[str] = set()
        self._notificadas = 0
        self._fin_enviado = False

    @property
    def puerto(self) -> int:
        return self.escucha.getsockname()[1]

    # --- bucle ------------------------------------------------------------------------------------
    def servir(self, parar=None) -> None:
        """Bucle real: espera mensajes como mucho 1/30 s y avanza con el dt medido. `parar` es un Event."""
        antes = time.monotonic()
        while parar is None or not parar.is_set():
            self.atender(1 / 30)
            ahora = time.monotonic()
            self.paso(ahora - antes)
            antes = ahora
        self.cerrar()

    def cerrar(self) -> None:
        for sock in list(self.conexiones):
            self._desconectar(sock)
        self.selector.unregister(self.escucha)
        self.escucha.close()
        self.selector.close()

    def atender(self, espera: float = 0.0) -> None:
        for clave, eventos in self.selector.select(espera):
            sock = clave.fileobj
            if sock is self.escucha:
                nuevo, _ = self.escucha.accept()
                nuevo.setblocking(False)
                self.conexiones[nuevo] = Conexion(nuevo)
                self.selector.register(nuevo, selectors.EVENT_READ)
                continue
            if sock not in self.conexiones:
                continue
            if eventos & selectors.EVENT_READ:
                self._leer(sock)
            if sock in self.conexiones and eventos & selectors.EVENT_WRITE:
                self._escribir(sock)

    def _leer(self, sock: socket.socket) -> None:
        try:
            datos = sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            datos = b""
        if not datos:                       # el cliente cerro o se cayo la red
            self._desconectar(sock)
            return
        con = self.conexiones[sock]
        try:
            mensajes = con.lector.agregar(datos)
        except MensajeInvalido as e:        # flujo imposible de resincronizar: se cierra solo esa conexion
            self._enviar(con, {"tipo": "error", "motivo": f"flujo invalido: {e}"})
            self._escribir(sock)
            self._desconectar(sock)
            return
        for mensaje in mensajes:
            self._despachar(con, mensaje)

    def _escribir(self, sock: socket.socket) -> None:
        con = self.conexiones[sock]
        try:
            enviados = sock.send(con.salida)
            del con.salida[:enviados]
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            self._desconectar(sock)
            return
        if not con.salida:
            self.selector.modify(sock, selectors.EVENT_READ)

    def _enviar(self, con: Conexion, mensaje: dict) -> None:
        if con.sock not in self.conexiones:
            return
        con.salida += empaquetar(mensaje)
        if len(con.salida) > MAX_SALIDA:    # no lee: se lo desconecta antes de que llene la memoria
            self._desconectar(con.sock)
            return
        self.selector.modify(con.sock, selectors.EVENT_READ | selectors.EVENT_WRITE)

    def _a_todos(self, mensaje: dict) -> None:
        for con in list(self.conexiones.values()):
            if con.lugar is not None:
                self._enviar(con, mensaje)

    def _desconectar(self, sock: socket.socket) -> None:
        con = self.conexiones.pop(sock, None)
        if con is None:
            return
        if con.lugar is not None and self.sesion is not None:
            self._evento(f"{con.lugar['nombre']} se desconecto", con.lugar["jugador"], "malo")
        try:
            self.selector.unregister(sock)
        except (KeyError, ValueError):
            pass
        sock.close()
        lugar = con.lugar
        if lugar is None:
            return
        lugar["conexion"] = None
        if self.sesion is None:             # en la sala: se libera su lugar
            self.sala.remove(lugar)
        elif lugar["jugador"] is not None:  # en partida: su rol lo toma un aliado hasta que vuelva
            self.sesion.asignar(Role[lugar["rol"]], None)
            self.sesion.notificar("info", "Desconexion", f"{lugar['nombre']} se desconecto: lo cubre un aliado.")
        self._sala()

    # --- mensajes ---------------------------------------------------------------------------------
    def _despachar(self, con: Conexion, mensaje: dict) -> None:
        tipo = mensaje["tipo"]
        manejador = getattr(self, f"_m_{tipo}", None)
        try:
            if manejador is None or tipo.startswith("_"):
                raise Rechazo(mensaje.get("motivo", "tipo_desconocido") if tipo == "_invalido" else "tipo_desconocido")
            if tipo != "unirse" and con.lugar is None:
                raise Rechazo("primero_unirse")
            manejador(con, mensaje)
        except Rechazo as r:
            self._enviar(con, {"tipo": "error", "motivo": str(r), "para": tipo})
        except (KeyError, ValueError, TypeError) as e:   # datos mal formados: se rechaza, el servidor sigue
            self._enviar(con, {"tipo": "error", "motivo": f"datos_invalidos: {e}", "para": tipo})
        n = mensaje.get("n")
        if isinstance(n, int):
            con.ack = max(con.ack, n)

    def _evento(self, texto: str, jugador: str | None = None, tipo: str = "info", novedad: str = "") -> None:
        """Queda en las fotos que siguen: cada cliente lo muestra una sola vez (por su numero)."""
        n = self.eventos[-1]["n"] + 1 if self.eventos else 1
        self.eventos = self.eventos[-29:] + [{"n": n, "texto": texto, "jugador": jugador, "tipo": tipo,
                                              "novedad": novedad}]

    def _nombre(self, jid: str) -> str:
        return next((l["nombre"] for l in self.sala if l["jugador"] == jid), jid)

    def _sala(self) -> None:
        jugadores = [{"nombre": l["nombre"], "rol": l["rol"], "genero": l["genero"], "jugador": l["jugador"],
                      "conectado": l["conexion"] is not None, "anfitrion": i == 0} for i, l in enumerate(self.sala)]
        for i, l in enumerate(self.sala):   # a cada uno, cual es el (los nombres se pueden repetir)
            if l["conexion"] is not None:
                self._enviar(l["conexion"], {"tipo": "sala", "jugadores": jugadores, "yo": i})

    def _m_unirse(self, con: Conexion, m: dict) -> None:
        if con.lugar is not None:
            raise Rechazo("ya_unido")
        token = m.get("token")
        lugar = next((l for l in self.sala if token and l["token"] == token), None)
        if lugar is not None:               # vuelve tras una desconexion
            if lugar["conexion"] is not None:
                raise Rechazo("token_en_uso")
            lugar["conexion"], con.lugar = con, lugar
            if self.sesion is not None:
                self.sesion.asignar(Role[lugar["rol"]], lugar["jugador"])
                self._evento(f"{lugar['nombre']} volvio", lugar["jugador"], "bueno")
                self._enviar(con, {"tipo": "bienvenida", "token": lugar["token"], "jugador": lugar["jugador"]})
                self._enviar(con, {"tipo": "inicio", "jugador": lugar["jugador"], "sesion": self.sesion.to_dict()})
            else:
                self._enviar(con, {"tipo": "bienvenida", "token": lugar["token"], "jugador": None})
            self._sala()
            return
        if self.sesion is not None:
            raise Rechazo("partida_en_curso")
        if len(self.sala) >= MAX_JUGADORES:
            raise Rechazo("sala_llena")
        nombre = str(m.get("nombre") or f"Jugador {len(self.sala) + 1}")[:24]
        lugar = {"nombre": nombre, "token": secrets.token_hex(8), "rol": None, "genero": "MUJER", "jugador": None,
                 "conexion": con}
        self.sala.append(lugar)
        con.lugar = lugar
        self._enviar(con, {"tipo": "bienvenida", "token": lugar["token"], "jugador": None})
        self._sala()

    def _m_elegir_rol(self, con: Conexion, m: dict) -> None:
        if self.sesion is not None:
            raise Rechazo("partida_en_curso")
        rol, genero = Role[m["rol"]].name, Genero[m.get("genero", "MUJER")].name
        if any(l["rol"] == rol and l is not con.lugar for l in self.sala):
            raise Rechazo("rol_tomado")
        con.lugar["rol"], con.lugar["genero"] = rol, genero
        self._sala()

    def _m_iniciar(self, con: Conexion, m: dict) -> None:
        if self.sesion is not None:
            raise Rechazo("partida_en_curso")
        if con.lugar is not self.sala[0]:
            raise Rechazo("solo_el_anfitrion")
        if not MIN_JUGADORES <= len(self.sala) <= MAX_JUGADORES:
            raise Rechazo("faltan_jugadores")
        if any(l["rol"] is None for l in self.sala):
            raise Rechazo("faltan_roles")
        personajes = [Personaje(Role[l["rol"]], Genero[l["genero"]]) for l in self.sala]
        self.sesion = s = PartidaSesion.nueva_campana(
            personajes, load_trees(RUTA_EVENTOS), GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
            GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), self.rng, minijuegos=mj.cargar_lugares(RUTA_MINIJUEGOS))
        for lugar, j in zip(self.sala, s.jugadores):
            lugar["jugador"] = j.id
            centro = self.mapa.zonas[s.mapa.zona_inicial].centro
            self.posiciones[j.id] = {"pos": centro, "dir": "abajo", "t": self.t}
            s.situar(j.id, centro, s.mapa.zona_inicial)
        for lugar in self.sala:
            if lugar["conexion"] is not None:
                self._enviar(lugar["conexion"], {"tipo": "inicio", "jugador": lugar["jugador"],
                                                 "sesion": s.to_dict()})
        self._sala()

    def _jugador(self, con: Conexion) -> str:
        if self.sesion is None or con.lugar["jugador"] is None:
            raise Rechazo("sin_partida")
        return con.lugar["jugador"]

    def _m_posicion(self, con: Conexion, m: dict) -> None:
        """Valida contra el mapa y el grafo: ni muros, ni teletransportes, ni cruzar una frontera cerrada."""
        jid = self._jugador(con)
        s = self.sesion
        p = (float(m["x"]), float(m["y"]))
        previa = self.posiciones[jid]
        if not all(map(math.isfinite, p)):
            self._enviar(con, {"tipo": "corregir", "x": previa["pos"][0], "y": previa["pos"][1],
                               "motivo": "posicion_invalida"})
            return
        self.mapa.sincronizar(s.mapa)
        zona_antes, zona = s.jugador(jid).zona, self.mapa.zona_en(p)
        lejos = math.dist(p, previa["pos"]) > self.mapa.velocidad * HOLGURA_VELOCIDAD * max(
            FOTO, self.t - previa["t"]) + self.mapa.pies[0]
        cruza = zona is not None and zona != zona_antes and (
            zona not in s.mapa or zona_antes not in s.mapa or s.mapa.distancia(zona_antes, zona) is None)
        if self.mapa.bloqueado(p) or lejos or cruza:
            self._enviar(con, {"tipo": "corregir", "x": previa["pos"][0], "y": previa["pos"][1],
                               "motivo": "frontera_cerrada" if cruza else "posicion_invalida"})
            return
        self.posiciones[jid] = {"pos": p, "dir": str(m.get("dir", "abajo"))[:12], "t": self.t}
        s.situar(jid, p, zona)

    def _m_decidir(self, con: Conexion, m: dict) -> None:
        """Queda pendiente: quien decidio ve la propagacion y la cierra con `aplicar` (o se cierra sola)."""
        jid = self._jugador(con)
        r = self.sesion.decidir(jid, str(m["nodo"]))
        if not r.ok:
            raise Rechazo(r.motivo)
        self._espera = 0.0
        self._evento(f"{self._nombre(jid)} decidio: {r.nodo.label}", jid)

    def _m_aplicar(self, con: Conexion, m: dict) -> None:
        s, jid = self.sesion, self._jugador(con)
        if s.pendiente is None or s.pendiente.jugador != jid:
            raise Rechazo("sin_decision")
        s.aplicar()
        self._espera = 0.0

    def _m_ver(self, con: Conexion, m: dict) -> None:
        """El de turno abrio la noticia: desde aqui corre su reloj (si es viral)."""
        if self.sesion.jugador_actual.id != self._jugador(con):
            raise Rechazo("no_es_su_turno")
        self.sesion.iniciar_reloj()

    def _m_evidencia(self, con: Conexion, m: dict) -> None:
        self.sesion.buscar_evidencia(self._jugador(con))

    def _m_continuar(self, con: Conexion, m: dict) -> None:
        s, jid = self.sesion, self._jugador(con)
        if s.fase == CONSECUENCIA:
            if s.jugador_actual.id != jid:
                raise Rechazo("no_es_su_turno")
            s.continuar()
            self._espera = 0.0
        elif s.fase == FIN_DIA:
            self._listos.add(jid)
        else:
            raise Rechazo("fuera_de_fase")

    def _m_investigar(self, con: Conexion, m: dict) -> None:
        r = self.sesion.investigar(self._jugador(con), str(m["pista"]))
        if not r.ok:
            raise Rechazo(r.motivo)

    def _m_concluir(self, con: Conexion, m: dict) -> None:
        r = self.sesion.concluir(self._jugador(con), str(m["veredicto"]))
        if not r.ok:
            raise Rechazo(r.motivo)

    def _m_testimonio(self, con: Conexion, m: dict) -> None:
        s = self.sesion
        jid = self._jugador(con)
        t = next((t for t in s.testigos() if t.id == m["testigo"]), None)
        if t is None or not s.puede_hablar(t):
            raise Rechazo("testigo_no_disponible")
        s.anotar_testimonio(jid, t)

    def _m_escudo(self, con: Conexion, m: dict) -> None:
        self.escudos[self._jugador(con)] = ((_acotar(m["x"]), _acotar(m["y"])), self.t)

    def _m_onda(self, con: Conexion, m: dict) -> None:
        jid = self._jugador(con)
        r = self.sesion.onda((_acotar(m["x"]), _acotar(m["y"])))
        if not r.ok:
            raise Rechazo(r.motivo)
        self._evento(f"{self._nombre(jid)} lanzo un desmentido en onda", jid, "bueno")

    def _m_publicar(self, con: Conexion, m: dict) -> None:
        jid = self._jugador(con)
        ok, motivo, _ = self.sesion.publicar(posts.Post(**m["post"]), jid)
        if not ok:
            raise Rechazo(motivo)
        self._evento(f"{self._nombre(jid)} publico un post", jid)

    def _m_habilidad(self, con: Conexion, m: dict) -> None:
        jid = self._jugador(con)
        r = self.sesion.usar_habilidad(jid)
        if not r.ok:
            raise Rechazo(r.motivo)
        self._evento(f"{self._nombre(jid)} uso {roles.HABILIDADES[self.sesion.jugador(jid).rol].nombre}", jid, "bueno")

    def _m_ayuda(self, con: Conexion, m: dict) -> None:
        jid = self._jugador(con)
        rol = Role[m["rol"]]
        r = self.sesion.pedir_ayuda(rol)
        if not r.ok:
            raise Rechazo(r.motivo)
        self._evento(f"{self._nombre(jid)} pidio ayuda al {rol.value} aliado", jid)

    def _m_minijuego(self, con: Conexion, m: dict) -> None:
        """El minijuego se juega en el cliente (sin lag en las teclas); al terminar manda su estado y el servidor
        valida que estaba disponible ahi y para el, y aplica el resultado con las reglas de la sesion."""
        s, jid = self.sesion, self._jugador(con)
        d = m["terminar"]
        juego = mj.desde_dict({**d, "contexto": {**d["contexto"], "jugador": jid}})
        lugar = juego.contexto.lugar
        if (s.jugador(jid).zona != lugar or s.minijuegos.get(lugar) != juego.id or s.minijuego is not None
                or lugar in s.campana.minijuegos_hoy):   # uno por lugar y por dia, como en el modo individual
            raise Rechazo("minijuego_no_disponible")
        if not juego.terminado:
            raise Rechazo("minijuego_sin_terminar")
        s.minijuego = juego
        r = s.terminar_minijuego()
        self._evento(f"{self._nombre(jid)} jugo {juego.nombre}", jid, "bueno" if r.impacto.score >= 0 else "malo")

    def _m_salir(self, con: Conexion, m: dict) -> None:
        self._escribir(con.sock)
        self._desconectar(con.sock)

    # --- simulacion ---------------------------------------------------------------------------------
    def _conectado(self, jid: str) -> bool:
        return any(l["jugador"] == jid and l["conexion"] is not None for l in self.sala)

    def paso(self, dt: float) -> None:
        """Avanza la sesion (autoritativa) y cada FOTO segundos manda el estado a todos."""
        self.t += dt
        s = self.sesion
        if s is not None and s.fase != FIN:
            self._simular(dt * self.acelerar)
        self._foto += dt
        if s is not None and self._foto >= FOTO:
            self._foto = 0.0
            foto = self.foto()
            for con in list(self.conexiones.values()):
                if con.lugar is not None:
                    self._enviar(con, {**foto, "ack": con.ack})
        if s is not None and s.fase == FIN and not self._fin_enviado:
            self._fin_enviado = True
            e = s.resultado_eleccion()
            self._a_todos({"tipo": "fin", "ganador": e.ganador, "votos": e.votos, "participacion": e.participacion,
                           "puntos": {j.id: j.puntos for j in s.jugadores}})

    def _simular(self, dt: float) -> None:
        s = self.sesion
        if s.fase == DECIDIENDO and s.pendiente is not None:   # se espera a que quien decidio vea la propagacion
            self._espera += dt
            if not self._conectado(s.pendiente.jugador) or self._espera >= self.auto_continuar:
                s.aplicar()
                self._espera = 0.0
        elif s.fase == DECIDIENDO:
            if not self._conectado(s.jugador_actual.id):   # su turno y no esta: se lo espera un rato
                self._espera += dt
                if self._espera >= self.gracia:
                    ramas = s.arbol.root.children
                    nodo = next((n for n in ramas if n.tipo == "ignorar"), ramas[0])
                    s.decidir(s.jugador_actual.id, nodo)
                    s.aplicar()
                    self._espera = 0.0
                    return
            if s.transcurrir(dt) is not None:           # vencio un reloj viral: queda pendiente para que se vea
                self._espera = 0.0
            v = s.en_vivo
            if v is not None:                           # los escudos de quienes tienen el telefono abierto
                for pos, cuando in self.escudos.values():
                    if self.t - cuando <= ESCUDO_VIGENTE:
                        v.interceptar(pos, RADIO_ESCUDO, ASPECTO_RED)
        elif s.fase == CONSECUENCIA:
            self._espera += dt
            if not self._conectado(s.jugador_actual.id) or self._espera >= self.auto_continuar:
                s.continuar()
                self._espera = 0.0
        elif s.fase == FIN_DIA:
            self._espera += dt
            conectados = {l["jugador"] for l in self.sala if l["conexion"] is not None}
            if conectados <= self._listos or self._espera >= self.espera_dia:
                s.anunciar_fase = False                 # solo queda en True si el dia nuevo empieza una fase
                s.empezar_siguiente_dia()
                self._listos.clear()
                self._espera = 0.0
                for j in s.jugadores:                   # amanece en la Plaza
                    centro = self.mapa.zonas[s.mapa.zona_inicial].centro
                    self.posiciones[j.id] = {"pos": centro, "dir": "abajo", "t": self.t}
                    s.situar(j.id, centro, s.mapa.zona_inicial)
        if s.novedad:                                   # crisis, viral o mapa: cada cliente la avisa una vez
            self._evento(s.notificaciones[-1]["titulo"] if s.notificaciones else s.novedad, None, "info", s.novedad)
            s.novedad = ""

    def foto(self) -> dict:
        """La sesion completa (unos 21 KB: el cliente la copia tal cual) y, aparte, lo que el cliente usa sin
        reconstruirla: posiciones con su direccion, nombres, conexion y los eventos numerados."""
        s = self.sesion
        c, v = s.campana, s.en_vivo
        nuevas, self._notificadas = s.notificaciones[self._notificadas:], len(s.notificaciones)
        nombres = {l["jugador"]: l["nombre"] for l in self.sala}
        return {
            "tipo": "estado", "t": round(self.t, 3), "fase": s.fase, "dia": c.dia, "t_dia": round(c.t, 2),
            "duracion_dia": c.duracion, "fase_campana": s.fase_campana, "indice": s.indice,
            "turno": s.jugador_actual.id, "zona_noticia": s.zona_noticia,
            "reloj": round(s.tiempo_restante, 2) if s.reloj_activo else None, "ciudad": s.ciudad.to_dict(),
            "jugadores": [{"id": j.id, "nombre": nombres.get(j.id, j.id), "rol": j.rol.name,
                           "pos": list(self.posiciones.get(j.id, {}).get("pos", j.posicion or (0, 0))),
                           "dir": self.posiciones.get(j.id, {}).get("dir", "abajo"), "zona": j.zona,
                           "en_zona": j.en_zona, "credibilidad": j.credibilidad, "puntos": j.puntos,
                           "conectado": self._conectado(j.id)} for j in s.jugadores],
            "ciudad_grafo": {"abiertas": [z.id for z in s.mapa.zonas()], "cerradas": sorted(s.protestas),
                             "crisis": list(s.zonas_crisis), "aisladas": list(s.aisladas)},
            "rumor": None if v is None else {"estado": v.estado, "frenados": v.frenados, "progreso": v.progreso_paso,
                                             "viajes": [list(x) for x in v.viajes]},
            "notificaciones": nuevas, "eventos": self.eventos, "sesion": s.to_dict(),
        }


def _acotar(x) -> float:
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("no es un numero")
    return min(1.0, max(0.0, x))


def main() -> None:
    p = argparse.ArgumentParser(description="Servidor del multijugador de Post & Truth")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--puerto", type=int, default=5050)
    args = p.parse_args()
    servidor = Servidor(args.host, args.puerto)
    print(f"Servidor escuchando en {args.host}:{servidor.puerto} (Ctrl+C para cerrar)")
    try:
        servidor.servir()
    except KeyboardInterrupt:
        servidor.cerrar()


if __name__ == "__main__":
    main()
