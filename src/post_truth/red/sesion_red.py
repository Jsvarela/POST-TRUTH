"""Sesion espejo del cliente (R12). Es una PartidaSesion como la del modo individual, asi que las pantallas la leen
igual; pero la autoridad es el servidor:

- Cada foto (10 por segundo) trae la sesion completa y la reemplaza. Se descarta mientras no confirme (`ack`)
  todas las acciones que este cliente ya mando: asi una foto vieja no deshace lo que el jugador acaba de hacer.
- Cada accion se predice en local (la misma regla de la sesion, con el mismo azar copiado del servidor, da el
  mismo resultado) y se manda al servidor, que la valida y la aplica de verdad.
- `transcurrir` no simula: solo adelanta el reloj, el rumor y los enfriamientos entre foto y foto para que se vean
  fluidos. Crisis, fin del dia, decisiones por tiempo y cambios del mapa llegan del servidor.
- `jugador_actual` es este cliente (el que camina, investiga y ve su credibilidad); `de_turno`, quien decide.
"""
from __future__ import annotations

from post_truth.models import posts
from post_truth.models import minijuego as mj
from post_truth.sesion import (CONSECUENCIA, DECIDIENDO, FIN_DIA, Jugador, PartidaSesion, ResultadoConclusion,
                               ResultadoDecision, ResultadoInvestigar)
from post_truth.structures.propagacion_vivo import ResultadoAccion

RETRASO = 0.1           # a los demas se los dibuja 100 ms atras: casi siempre hay dos fotos entre las que interpolar
ENVIO = 0.1             # posicion y escudo, 10 veces por segundo
ESCUDO_ACTIVO = 0.2     # el escudo se manda mientras se haya movido hace menos que esto
MUESTRAS = 12           # fotos que se guardan por jugador remoto
MOTIVOS = {"no_es_su_turno": "Espera tu turno.", "minijuego_no_disponible": "Ese minijuego ya no esta disponible.",
           "enfriando": "Aun se esta recargando.", "sin_rumor": "No hay un rumor corriendo ahora.",
           "fuera_de_paso": "Ahora no: la historia te lo ofrecera en su momento."}


def _direccion(dx: float, dy: float, previa: str) -> str:
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return previa
    if abs(dx) > abs(dy):
        return "derecha" if dx > 0 else "izquierda"
    return "abajo" if dy > 0 else "arriba"


class SesionEnRed(PartidaSesion):
    en_red = True

    @classmethod
    def desde_inicio(cls, mensaje: dict, conexion) -> "SesionEnRed":
        """`inicio` del servidor: la sesion completa y quien es este cliente."""
        s = cls.from_dict(mensaje["sesion"])
        s.yo, s.conexion = mensaje["jugador"], conexion
        s.n = 0                          # numero de la ultima accion enviada
        s.evento_visto = 0
        s.acciones: list[tuple[str, str, str]] = []   # (titulo, texto, tipo) para los avisos de la pantalla
        s.correccion: tuple[float, float] | None = None
        s.nombres: dict[str, str] = {}
        s.conectados: dict[str, bool] = {}
        s.remotos: dict[str, list[tuple[float, tuple[float, float], str]]] = {}
        s.reloj = 0.0                    # tiempo local
        s._t_servidor, s._recibida = 0.0, 0.0
        s.t_dibujo = 0.0                 # instante del servidor en que se dibuja a los demas (nunca retrocede)
        s._t_envio = 0.0
        s._enviada: tuple[float, float] | None = None
        s.direccion = "abajo"
        s._escudo: tuple[tuple[float, float], float] | None = None
        s._vencida: ResultadoDecision | None = None
        s.esperando = False              # fin del dia: ya paso el resumen y espera a los demas
        s.fin: dict | None = None
        return s

    # --- quien es quien ------------------------------------------------------------------------
    @property
    def jugador_actual(self) -> Jugador:
        yo = self.__dict__.get("yo")
        return super().jugador_actual if yo is None else self.jugador(yo)

    @property
    def de_turno(self) -> Jugador:
        return self.jugadores[(self.indice + self.turno) % len(self.jugadores)]

    @property
    def es_mi_turno(self) -> bool:
        return self.de_turno.id == self.yo

    def nombre(self, jid: str) -> str:
        return self.nombres.get(jid, jid)

    # --- red -----------------------------------------------------------------------------------
    def _enviar(self, tipo: str, **datos) -> None:
        self.n += 1
        self.conexion.enviar({"tipo": tipo, "n": self.n, **datos})

    def _predecir(self, accion):
        """Una regla de la sesion en local, sin que levante avisos: las novedades las manda el servidor."""
        antes = self.novedad
        r = accion()
        self.novedad = antes
        return r

    def tick(self, dt: float) -> None:
        """Cada cuadro, desde el bucle: lee la cola (sin esperar) y manda posicion y escudo a su ritmo."""
        self.reloj += dt
        for m in self.conexion.recibir():
            self.recibir(m)
        objetivo = self._t_servidor + (self.reloj - self._recibida) - RETRASO
        if abs(objetivo - self.t_dibujo) > 1.0:   # muy desfasado (inicio, pausa larga): se salta
            self.t_dibujo = objetivo
        else:   # las fotos llegan con algo de jitter: se corrige de a poco y sin ir hacia atras
            self.t_dibujo = max(self.t_dibujo, self.t_dibujo + dt + (objetivo - self.t_dibujo - dt) * min(1.0, 4 * dt))
        if self.reloj - self._t_envio < ENVIO:
            return
        self._t_envio = self.reloj
        pos = self.jugador(self.yo).posicion
        if pos is not None and pos != self._enviada:
            if self._enviada is not None:
                self.direccion = _direccion(pos[0] - self._enviada[0], pos[1] - self._enviada[1], self.direccion)
            self._enviada = pos
            self.conexion.enviar({"tipo": "posicion", "x": pos[0], "y": pos[1], "dir": self.direccion})
        if self._escudo is not None and self.reloj - self._escudo[1] <= ESCUDO_ACTIVO:
            self.conexion.enviar({"tipo": "escudo", "x": self._escudo[0][0], "y": self._escudo[0][1]})

    def recibir(self, m: dict) -> None:
        tipo = m.get("tipo")
        if tipo == "estado":
            self._foto(m)
        elif tipo == "corregir":
            self.correccion = (float(m["x"]), float(m["y"]))
            self._enviada = self.correccion
        elif tipo == "error":
            motivo = str(m.get("motivo", ""))
            self.acciones.append(("No se pudo", MOTIVOS.get(motivo, motivo.replace("_", " ")), "malo"))
        elif tipo == "fin":
            self.fin = m

    def _foto(self, m: dict) -> None:
        for j in m.get("jugadores", []):
            self.nombres[j["id"]], self.conectados[j["id"]] = j["nombre"], j["conectado"]
            if j["id"] != self.yo:
                muestras = self.remotos.setdefault(j["id"], [])
                muestras.append((float(m["t"]), (float(j["pos"][0]), float(j["pos"][1])), j["dir"]))
                del muestras[:-MUESTRAS]
        self._t_servidor, self._recibida = float(m["t"]), self.reloj
        for e in m.get("eventos", []):
            if e["n"] <= self.evento_visto:
                continue
            self.evento_visto = e["n"]
            if e.get("novedad"):
                self.novedad = "crisis" if "crisis" in (self.novedad, e["novedad"]) else e["novedad"]
            elif e.get("jugador") != self.yo:
                self.acciones.append(("Otros jugadores", e["texto"], e.get("tipo", "info")))
        if m.get("ack", 0) >= self.n and "sesion" in m:
            self.aplicar_foto(m["sesion"])

    def aplicar_foto(self, datos: dict) -> None:
        """Reemplaza el estado por el del servidor, conservando lo que es solo de este cliente."""
        nueva = PartidaSesion.from_dict(datos)
        pendiente, minijuego, turno = self.pendiente, self.minijuego, self.de_turno.id
        dia_antes = self.campana.dia if self.campana is not None else None   # amanece: vale la del servidor
        leidas, novedad, charla = self.leidas, self.novedad, self.charla
        yo = self.jugador(self.yo)
        donde = yo.posicion, yo.en_zona, yo.zona   # el movimiento propio es local; el servidor corrige con `corregir`
        vars(self.ciudad).update(vars(nueva.ciudad))   # misma ciudad: el HUD anima el cambio, no lo toma por otra
        nueva.ciudad = self.ciudad
        vars(self).update(vars(nueva))
        self.leidas, self.novedad, self.charla = min(leidas, len(self.notificaciones)), novedad, charla   # la charla es local
        if self.campana is None or self.campana.dia == dia_antes:
            yo = self.jugador(self.yo)
            yo.posicion, yo.en_zona, yo.zona = donde
        if minijuego is not None and minijuego.contexto.jugador == self.yo:   # el minijuego corre aqui
            self.minijuego = minijuego
        p = self.pendiente
        if p is not None and pendiente is not None and (p.jugador, p.nodo.node_id) == (pendiente.jugador,
                                                                                       pendiente.nodo.node_id):
            self.pendiente = pendiente    # la prediccion trae la simulacion para la animacion
        elif p is not None and p.vencido and p.jugador == self.yo:
            self._vencida = p             # se acabo mi reloj: la pantalla lo muestra
        if self.fase != FIN_DIA:
            self.esperando = False
        if self.de_turno.id != turno and self.fase == DECIDIENDO:
            self.acciones.append(("Tu turno", "Te toca decidir la noticia.", "bueno") if self.es_mi_turno else
                                 ("Turno", f"Ahora decide {self.nombre(self.de_turno.id)}.", "info"))

    def remotos_en(self, t: float | None = None) -> list[tuple[str, tuple[float, float], str, bool]]:
        """(id, posicion, direccion, caminando) de los demas en el instante `t` del servidor (por defecto
        `t_dibujo`, RETRASO atras del ultimo), interpolando entre las dos fotos que lo rodean. Sin dos fotos que
        lo rodeen, la mas cercana: nunca se adivina hacia adelante."""
        t = self.t_dibujo if t is None else t
        salida = []
        for jid, muestras in self.remotos.items():
            if not muestras:
                continue
            previa = next((a for a in reversed(muestras) if a[0] <= t), muestras[0])
            siguiente = next((b for b in muestras if b[0] > t), muestras[-1])
            if siguiente[0] > previa[0]:
                f = min(1.0, max(0.0, (t - previa[0]) / (siguiente[0] - previa[0])))
            else:
                f = 1.0
            pos = (previa[1][0] + (siguiente[1][0] - previa[1][0]) * f,
                   previa[1][1] + (siguiente[1][1] - previa[1][1]) * f)
            salida.append((jid, pos, siguiente[2], previa[1] != siguiente[1]))
        return salida

    # --- reloj: solo cosmetico entre fotos -------------------------------------------------------
    def transcurrir(self, dt: float) -> ResultadoDecision | None:
        if self.fase == DECIDIENDO and self.pendiente is None and self.campana is not None:
            c = self.campana
            if self.reloj_activo and self.tiempo_restante is not None:
                self.tiempo_restante = max(0.0, self.tiempo_restante - dt)
            self.avanzar_rumor(dt)
            if self.calle is not None:   # los transeuntes caminan igual que en el servidor (sin regar: eso es de el)
                self.calle.actualizar(dt, self.mapa)
            self.enfriamiento_post = max(0.0, self.enfriamiento_post - dt)
            for k in self.enfriamientos:
                self.enfriamientos[k] = max(0.0, self.enfriamientos[k] - dt)
        vencida, self._vencida = self._vencida, None
        return vencida

    def avanzar_rumor(self, dt: float) -> None:
        v = self.en_vivo
        if v is not None and self.campana is not None and not v.terminada:
            v.avanzar(dt / self.campana.factor)

    # --- acciones: prediccion local + mensaje al servidor ----------------------------------------
    def decidir(self, jugador: str, accion) -> ResultadoDecision:
        if not self.es_mi_turno:
            return ResultadoDecision(False, "no_es_su_turno", jugador)
        r = self._predecir(lambda: super(SesionEnRed, self).decidir(self.yo, accion))
        if r.ok:
            self._enviar("decidir", nodo=r.nodo.node_id)
        return r

    def aplicar(self) -> ResultadoDecision:
        r = self._predecir(super().aplicar)
        if r.jugador == self.yo:
            self._enviar("aplicar")
        return r

    def continuar(self) -> bool:
        if self.fase != CONSECUENCIA or not self.es_mi_turno:
            return False
        r = self._predecir(super().continuar)
        self._enviar("continuar")
        return r

    def empezar_siguiente_dia(self) -> bool:
        """El resumen ya se vio: el servidor sigue cuando todos lo pasan (la pantalla espera la foto)."""
        if self.fase == FIN_DIA and not self.esperando:
            self.esperando = True
            self._enviar("continuar")
        return False

    def iniciar_reloj(self) -> None:
        if self.es_mi_turno and self.fase == DECIDIENDO and self.tiempo_restante is not None and not self.reloj_activo:
            super().iniciar_reloj()
            self._enviar("ver")

    def investigar(self, jugador: str, pista) -> ResultadoInvestigar:
        if not self.es_mi_turno:
            return ResultadoInvestigar(False, "no_es_su_turno")
        r = super().investigar(self.yo, pista)
        if r.ok:
            self._enviar("investigar", pista=r.pista.id if r.pista is not None else getattr(pista, "id", pista))
        return r

    def anotar_testimonio(self, jugador: str, t) -> None:
        if self.es_mi_turno:
            super().anotar_testimonio(self.yo, t)
            self._enviar("testimonio", testigo=t.id)

    def concluir(self, jugador: str, veredicto: str) -> ResultadoConclusion:
        if not self.es_mi_turno:
            return ResultadoConclusion(False, "no_es_su_turno")
        r = super().concluir(self.yo, veredicto)
        if r.ok:
            self._enviar("concluir", veredicto=veredicto)
        return r

    def buscar_evidencia(self, jugador: str):
        if not self.es_mi_turno:
            return None
        e = super().buscar_evidencia(self.yo)
        self._enviar("evidencia")
        return e

    def terminar_minijuego(self) -> mj.ResultadoMinijuego:
        estado = self.minijuego.to_dict() if self.minijuego is not None else None
        r = self._predecir(super().terminar_minijuego)
        self._enviar("minijuego", terminar=estado)
        return r

    def publicar(self, post: posts.Post, jugador: str | None = None):
        r = self._predecir(lambda: super(SesionEnRed, self).publicar(post, self.yo))
        if r[0]:
            self._enviar("publicar", post=post.to_dict())
        return r

    def usar_habilidad(self, jugador: str) -> ResultadoAccion:
        if not self.es_mi_turno:
            return ResultadoAccion(False, "no_es_su_turno")
        r = self._predecir(lambda: super(SesionEnRed, self).usar_habilidad(self.yo))
        if r.ok:
            self._enviar("habilidad")
        return r

    def pedir_ayuda(self, rol) -> ResultadoAccion:
        r = self._predecir(lambda: super(SesionEnRed, self).pedir_ayuda(rol))
        if r.ok:
            self._enviar("ayuda", rol=rol.name)
        return r

    def cerrar_encuentro(self, jugador: str, id: str, como: str) -> str:
        r = super().cerrar_encuentro(self.yo, id, como)
        if r:
            self._enviar("encuentro", id=id, como=como)
        return r

    def onda(self, centro: tuple[float, float]) -> ResultadoAccion:
        r = super().onda(centro)
        if r.ok:
            self._enviar("onda", x=centro[0], y=centro[1])
        return r

    def escudo(self, centro: tuple[float, float], radio: float) -> bool:
        self._escudo = (centro, self.reloj)
        return super().escudo(centro, radio)
