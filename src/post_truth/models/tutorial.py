""""Como se juega" (video interactivo) antes de un minijuego: primero el motor juega solo una copia con `demo()`
y subtitulos paso a paso (se repite hasta que el jugador quiera practicar); despues una practica sin consecuencias
con otra copia; con 3 aciertos queda "listo". Nada de esto toca la partida."""
from __future__ import annotations

from dataclasses import replace

from post_truth.models import minijuego as mj

PASO = 3.2           # segundos por subtitulo en la demostracion
ACIERTOS_PRACTICA = 3
TECLAS_VISIBLES = {"1", "2", "3", "espacio", "disparo"}   # las que se resaltan en pantalla (girar o apuntar no)


def tiene_tutorial(id: str) -> bool:
    return bool(mj.REGISTRO[id].pasos_tutorial)


class Tutorial:
    def __init__(self, id: str, contexto: mj.ContextoMinijuego) -> None:
        self.id = id
        # en la demo y la practica sobra municion y evidencia: se aprende la mecanica, no se gasta lo investigado
        self.contexto = replace(contexto, municion={"pista": 9, "evidencia": 9, "testimonio": 9}, evidencias=9)
        self.pasos = mj.REGISTRO[id].pasos_tutorial
        self.fase = "demo"            # demo -> practica -> listo -> fin
        self.juego = mj.crear(id, self.contexto)
        self.t, self.tecla, self.aciertos = 0.0, "", 0

    @property
    def paso(self) -> str:
        return self.pasos[min(int(self.t / PASO), len(self.pasos) - 1)] if self.fase == "demo" else ""

    def update(self, dt: float) -> None:
        if self.fase == "fin":
            return
        self.t += dt
        if self.fase == "demo":
            for a in self.juego.demo():
                self.juego.accion(a)
                if a in TECLAS_VISIBLES:
                    self.tecla = a
            if self.juego.terminado or self.t >= PASO * len(self.pasos) + 2:   # el "video" vuelve a empezar
                self.juego, self.t = mj.crear(self.id, self.contexto), 0.0
        self.juego.update(dt)
        if self.fase == "practica":
            self.aciertos += self.juego.ecos.count("acierto")
            if self.aciertos >= ACIERTOS_PRACTICA:
                self.fase = "listo"
            elif self.juego.terminado:   # se acabo sin llegar: otra ronda de practica
                self.juego = mj.crear(self.id, self.contexto)
        self.juego.ecos.clear()

    def accion(self, nombre: str) -> None:
        """El teclado del jugador: solo cuenta en la practica."""
        if self.fase in ("practica", "listo"):
            self.juego.accion(nombre)

    def avanzar(self) -> None:
        """Enter: de la demo a la practica; de la practica (o listo) a jugar de verdad."""
        if self.fase == "demo":
            self.fase, self.juego, self.tecla = "practica", mj.crear(self.id, self.contexto), ""
        else:
            self.fase = "fin"
