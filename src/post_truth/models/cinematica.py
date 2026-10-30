"""Cinematicas en el motor (L3): guiones de data/cinematicas.json sobre el mapa real. Logica pura, sin pygame.

COMO SE RECORRE UN GUION: es una lista de comandos y el interprete lleva un contador de programa (`pc`, el indice
del comando actual). Cada `update(dt)` avanza el comando actual con el tiempo transcurrido; cuando ese comando
termina (la camara llego, el actor llego, el dialogo se cerro, paso la espera) el contador sube y en el mismo
cuadro arranca el siguiente. Un comando con "sin_esperar" arranca y queda corriendo en `fondo` mientras el
contador sigue (un actor camina mientras otro habla). Un comando con "si" se evalua al llegarle el turno contra el
contexto (una foto de la partida) y, si no se cumple, se salta. Es un recorrido lineal O(n) sobre la lista, sin
hilos ni esperas: el bucle del juego nunca se bloquea.

Los actores, la camara y la noche viven solo aqui: la cinematica no cambia la partida.
"""
from __future__ import annotations

import json
import math
import operator
import re
from functools import lru_cache

from post_truth.config import RUTA_CINEMATICAS, RUTA_MAPA
from post_truth.models.animacion import DIRECCIONES, AnimacionPersonaje
from post_truth.structures.rutas import Geometria

# comando -> campos obligatorios
COMANDOS = {"actor": ("id", "en"), "quitar": ("id",), "caminar": ("id", "a"), "girar": ("id", "dir"),
            "camara": ("a",), "decir": ("texto",), "esperar": ("segundos",), "fundido": ("a",),
            "cartel": ("texto",), "sacudir": (), "noche": ("on",), "sonido": ("nombre",), "ciudad": ()}
EN_FONDO = {"caminar", "camara", "esperar", "fundido", "sacudir"}   # los que pueden ir "sin_esperar"
CON_TIEMPO = EN_FONDO | {"decir", "cartel"}   # los demas son instantaneos: no gastan el dt del cuadro
CLAVES = {"credibilidad", "desinformacion", "conflictos", "confianza", "verificada", "convivencia", "bienestar",
          "dia", "fase", "crisis", "aislada", "cerrada", "acierto", "pistas", "noticia", "escucho",
          "verdad"}   # lo que un "si" puede preguntar
VELOCIDAD_TEXTO = 40.0       # letras por segundo
VELOCIDAD_ACTOR = 140.0      # px del mapa por segundo
LEER = (1.2, 1 / 30)         # avance solo: espera 1.2 s + 1/30 s por letra con el texto completo
OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt, "==": operator.eq}
CONDICION = re.compile(r"(!?)(\w+)(?::([\w|-]+))?(?:(>=|<=|==|>|<)(-?\d+))?")


class GuionInvalido(ValueError):
    pass


def validar(id: str, guion: list[dict]) -> None:
    """Falla al cargar, no a mitad de la escena."""
    for i, c in enumerate(guion):
        donde = f"{id}[{i}]"
        if c.get("cmd") not in COMANDOS:
            raise GuionInvalido(f"{donde}: comando desconocido {c.get('cmd')!r}")
        faltan = [k for k in COMANDOS[c["cmd"]] if k not in c]
        if faltan:
            raise GuionInvalido(f"{donde}: le falta {faltan}")
        if c.get("sin_esperar") and c["cmd"] not in EN_FONDO:
            raise GuionInvalido(f"{donde}: {c['cmd']} no puede ir sin_esperar")
        if c["cmd"] in ("girar", "actor") and c.get("dir", "abajo") not in DIRECCIONES:
            raise GuionInvalido(f"{donde}: direccion {c.get('dir')!r}")
        for cond in c.get("si", ()):
            m = CONDICION.fullmatch(cond)
            if m is None or m.group(2) not in CLAVES:
                raise GuionInvalido(f"{donde}: condicion {cond!r}")


@lru_cache(maxsize=1)
def guiones() -> dict[str, list[dict]]:
    with RUTA_CINEMATICAS.open("r", encoding="utf-8") as f:
        datos = json.load(f)
    for id, guion in datos.items():
        validar(id, guion)
    return datos


@lru_cache(maxsize=1)
def geometria() -> Geometria:
    return Geometria.cargar(RUTA_MAPA)


def cumple(cond: str, ctx: dict) -> bool:
    """"crisis" (verdadero si hay algo), "!crisis", "crisis:barrio" (pertenece), "credibilidad>=60"."""
    neg, clave, arg, op, n = CONDICION.fullmatch(cond).groups()
    v = ctx.get(clave)
    if arg is not None:
        r = arg in (v or ())
    elif op is not None:
        r = v is not None and OPS[op](v, int(n))
    else:
        r = bool(v)
    return r != bool(neg)


def contexto(s) -> dict:
    """Foto de solo lectura de la partida para las condiciones (vacia sin partida)."""
    if s is None:
        return {}
    c, j = s.ciudad, s.jugador_actual
    inv = j.investigacion
    return {"credibilidad": j.credibilidad, "desinformacion": c.misinformation, "conflictos": c.conflicts,
            "confianza": c.trust, "verificada": c.verified_information, "convivencia": c.coexistence,
            "bienestar": c.digital_wellbeing, "dia": s.campana.dia + 1 if s.campana else 0,
            "fase": s.fase_campana + 1, "crisis": set(s.zonas_crisis), "aislada": set(s.aisladas),
            "cerrada": set(s.protestas), "acierto": inv.acierto is True, "pistas": len(inv.descubiertas),
            "noticia": {s.arbol.event.event_id}, "escucho": set(s.escuchados), "verdad": set(s.pistas_verdad),
            "personaje": (j.personaje.rol.name, j.personaje.genero.name, j.personaje.apariencia)}


class Interprete:
    def __init__(self, guion: list[dict], ctx: dict | None = None, camara: tuple[float, float] = (0.0, 0.0),
                 manual: bool = False) -> None:
        self.guion, self.ctx, self.manual = list(guion), ctx or {}, manual   # copia: "ciudad" inserta comandos
        self.pc = 0
        self.fondo: list[dict] = []          # comandos "sin_esperar" que siguen corriendo
        self.actual: dict | None = None      # el comando en curso, con su estado ("_t", ...)
        self.camara = camara
        self.sigue: str | None = None        # actor que la camara sigue
        self.actores: dict[str, dict] = {}   # id -> {nombre, rol, genero, variante, pos, anim}
        self.dialogo: dict | None = None     # {quien, texto, retrato, visibles}
        self.cartel: tuple[str, str] | None = None
        self.negro = 0.0                     # 0 claro .. 1 negro
        self.sacudida = (0.0, 0.0)           # (segundos que quedan, fuerza)
        self.noche = False
        self.sonidos: list[str] = []         # la pantalla los toca y vacia
        self.terminado = not guion
        self.t = 0.0

    # --- recorrido -------------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        self.fondo = [c for c in self.fondo if not self._correr(c, dt)]
        if self.sacudida[0] > 0:
            self.sacudida = (max(0.0, self.sacudida[0] - dt), self.sacudida[1])
        if self.sigue in self.actores:
            self.camara = tuple(self.actores[self.sigue]["pos"])
        for _ in range(len(self.guion) + 1):   # varios instantaneos pueden terminar en el mismo cuadro
            if self.actual is None and not self._siguiente():
                break
            if not self._correr(self.actual, dt):
                break
            self._cerrar(self.actual)
            if self.actual["cmd"] in CON_TIEMPO:
                dt = 0.0
            self.actual = None
        if self.actual is None and self.pc >= len(self.guion) and not self.fondo:
            self.terminado = True

    def _siguiente(self) -> bool:
        """Toma el proximo comando que cumpla su "si"; los "sin_esperar" se van al fondo."""
        while self.pc < len(self.guion):
            c = dict(self.guion[self.pc], _t=0.0)
            self.pc += 1
            if not all(cumple(x, self.ctx) for x in c.get("si", ())):
                continue
            if c["cmd"] == "ciudad":   # se reemplaza por lo que cambio en la ciudad
                self.guion[self.pc:self.pc] = self._ciudad(c)
                continue
            self._empezar(c)
            if c.get("sin_esperar"):
                self.fondo.append(c)
                continue
            self.actual = c
            return True
        return False

    def _ciudad(self, c: dict) -> list[dict]:
        """Mostrar, no solo contar: la camara va a cada calle cerrada, zona en crisis o aislada (del contexto)."""
        geo, cmds = geometria(), []
        for clave in sorted(self.ctx.get("cerrada", ())):
            a, b = clave.split("|")
            if geo.paso(a, b) is not None:
                cmds += [{"cmd": "camara", "a": list(geo.paso(a, b)), "segundos": 1.2},
                         {"cmd": "sacudir", "segundos": 0.3, "fuerza": 6},
                         {"cmd": "decir", "quien": "Civitas",
                          "texto": f"Protesta: cerraron la calle entre {a.capitalize()} y {b.capitalize()}."}]
        for clave, texto in (("crisis", "esta en crisis: alli los rumores corren mas rapido."),
                             ("aislada", "quedo aislada: no le llegan los desmentidos.")):
            for z in sorted(self.ctx.get(clave, ())):
                if z in geo.centros:
                    cmds += [{"cmd": "camara", "a": z, "segundos": 1.2},
                             {"cmd": "decir", "quien": "Civitas", "texto": f"{z.capitalize()} {texto}"}]
        return cmds or [{"cmd": "decir", "quien": "Civitas", "texto": c.get("calma", "Las calles siguen abiertas.")}]

    def avanzar(self) -> None:
        """Enter: completa el texto; si ya estaba completo, cierra el dialogo o el cartel."""
        c = self.actual
        if c is None:
            return
        if c["cmd"] == "decir":
            d = self.dialogo
            if d["visibles"] < len(d["texto"]):
                d["visibles"] = float(len(d["texto"]))
            else:
                c["_listo"] = True
        elif c["cmd"] == "cartel":
            c["_listo"] = True

    def saltar(self) -> None:
        """ESC: termina ya. Como nada toca la partida, no hay nada que deshacer."""
        self.terminado, self.dialogo, self.cartel, self.fondo, self.actual = True, None, None, [], None

    # --- cada comando ----------------------------------------------------------------------------
    def punto(self, a) -> tuple[float, float]:
        """Una zona ("plaza"), un actor ({"actor": id}) o un punto [x, y] del mapa."""
        if isinstance(a, str):
            return tuple(geometria().centros[a])
        if isinstance(a, dict):
            return tuple(self.actores[a["actor"]]["pos"])
        return float(a[0]), float(a[1])

    def _empezar(self, c: dict) -> None:
        cmd = c["cmd"]
        if cmd == "actor":
            rol, genero, variante = (self.ctx.get("personaje", ("CITIZEN", "MUJER", 0)) if c.get("jugador")
                                     else (c.get("rol", "CITIZEN"), c.get("genero", "MUJER"), c.get("variante", 0)))
            self.actores[c["id"]] = {"nombre": c.get("nombre", c["id"]), "rol": rol, "genero": genero,
                                     "variante": variante,
                                     "pos": list(self.punto(c["en"])),
                                     "anim": AnimacionPersonaje(c.get("dir", "abajo"))}
        elif cmd == "quitar":
            self.actores.pop(c["id"], None)
            if self.sigue == c["id"]:
                self.sigue = None
        elif cmd == "girar":
            self.actores[c["id"]]["anim"].direccion = c["dir"]
        elif cmd == "camara":
            if "seguir" in c:
                self.sigue = c["seguir"]
            else:
                self.sigue = None
                c["_desde"], c["_hasta"] = self.camara, self.punto(c["a"])
        elif cmd == "decir":
            self.dialogo = {"quien": c.get("quien", ""), "texto": c["texto"], "retrato": c.get("retrato"),
                            "visibles": 0.0}
        elif cmd == "cartel":
            self.cartel = (c["texto"], c.get("sub", ""))
        elif cmd == "sacudir":
            self.sacudida = (float(c.get("segundos", 0.5)), float(c.get("fuerza", 8)))
        elif cmd == "noche":
            self.noche = bool(c["on"])
        elif cmd == "sonido":
            self.sonidos.append(c["nombre"])

    def _correr(self, c: dict, dt: float) -> bool:
        """Avanza el comando `dt` segundos. True si termino."""
        c["_t"] += dt
        cmd = c["cmd"]
        if cmd == "caminar":
            return self._caminar(c, dt)
        if cmd == "camara":
            if "seguir" in c:
                return True
            dur = float(c.get("segundos", 1.0))
            f = 1.0 if dur <= 0 else min(1.0, c["_t"] / dur)
            f = f * f * (3 - 2 * f)   # suave al salir y al llegar
            (x0, y0), (x1, y1) = c["_desde"], c["_hasta"]
            self.camara = (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
            return f >= 1.0
        if cmd == "decir":
            d = self.dialogo
            d["visibles"] = min(float(len(d["texto"])), d["visibles"] + VELOCIDAD_TEXTO * dt)
            if d["visibles"] >= len(d["texto"]) and not self.manual:
                c["_leido"] = c.get("_leido", 0.0) + dt
                if c["_leido"] >= LEER[0] + LEER[1] * len(d["texto"]):
                    c["_listo"] = True
            return c.get("_listo", False)
        if cmd == "cartel":
            return c.get("_listo", False) or (not self.manual and c["_t"] >= float(c.get("segundos", 2.0)))
        if cmd == "fundido":
            objetivo = 1.0 if c["a"] == "negro" else 0.0
            dur = float(c.get("segundos", 0.6))
            paso = dt / dur if dur > 0 else 1.0
            self.negro = min(objetivo, self.negro + paso) if objetivo > self.negro else max(objetivo, self.negro - paso)
            return self.negro == objetivo
        if cmd in ("esperar", "sacudir"):
            return c["_t"] >= float(c.get("segundos", 0.5))
        return True   # instantaneos

    def _caminar(self, c: dict, dt: float) -> bool:
        a = self.actores[c["id"]]
        x, y = a["pos"]
        tx, ty = self.punto(c["a"])
        dx, dy = tx - x, ty - y
        d = math.hypot(dx, dy)
        paso = float(c.get("velocidad", VELOCIDAD_ACTOR)) * dt
        if d <= paso:
            a["pos"] = [tx, ty]
            a["anim"].actualizar(0, 0, 0.0, dt)   # llega: queda quieto mirando hacia donde iba
            return True
        a["pos"] = [x + dx / d * paso, y + dy / d * paso]
        a["anim"].actualizar(dx, dy, paso, dt)
        return False

    def _cerrar(self, c: dict) -> None:
        if c["cmd"] == "decir":
            self.dialogo = None
        elif c["cmd"] == "cartel":
            self.cartel = None

    @property
    def desplazamiento(self) -> tuple[float, float]:
        """Sacudida de la camara (px del mapa), que se apaga sola."""
        t, fuerza = self.sacudida
        if t <= 0:
            return 0.0, 0.0
        return fuerza * math.sin(self.t * 53) * min(1.0, t * 4), fuerza * math.cos(self.t * 41) * min(1.0, t * 4)
