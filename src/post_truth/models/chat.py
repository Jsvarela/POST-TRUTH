"""Minijuego del Colegio, "Chat bajo presion" (de accion): los mensajes del chat del curso caen por tres carriles.
Mueves a Sofi (izquierda/derecha) para atrapar los mensajes de apoyo y esquivar los ataques; tres apoyos llenan la
calma y Espacio la usa para borrar los ataques que hay en pantalla. Los textos salen del arbol de dialogo de
data/chat_colegio.json (ataques = lo que dicen los atacantes; apoyo = las respuestas que desescalan)."""
from __future__ import annotations

import json
import random
from functools import lru_cache

from post_truth.config import RUTA_CHAT
from post_truth.models.dominio import Impact
from post_truth.models.minijuego import ContextoMinijuego, Minijuego, ResultadoMinijuego, registrar
from post_truth.structures.arbol_dialogo import NodoDialogo

CARRILES = 3
FILA_SOFI = 0.86     # altura (0 arriba, 1 abajo) donde esta Sofi
CALMA_LLENA = 3
ATAQUE, APOYO = "ataque", "apoyo"


@lru_cache(maxsize=1)
def datos() -> tuple[dict, NodoDialogo]:
    with RUTA_CHAT.open("r", encoding="utf-8") as f:
        d = json.load(f)
    return d, NodoDialogo.from_dict(d["arbol"])


@lru_cache(maxsize=1)
def textos() -> dict[str, list[str]]:
    """Recorre el arbol (DFS) y separa lo que dicen los atacantes de las respuestas que desescalan."""
    ataques, apoyos = [], []

    def recorrer(n: NodoDialogo) -> None:
        if n.hablante.startswith("anonimo"):
            ataques.append(n.texto)
        for o in n.opciones:
            if o.tipo == "desescalar":
                apoyos.append(o.texto)
            if o.hijo is not None:
                recorrer(o.hijo)
    recorrer(datos()[1])
    return {ATAQUE: ataques, APOYO: apoyos}


@registrar
class Chat(Minijuego):
    id = "chat"
    nombre = "Chat bajo presion"
    ayuda = ("Atacan a Sofi en el chat del curso. Muevela con las flechas (o A/D) para atrapar los mensajes de apoyo "
             "(circulos verdes) y esquivar los ataques (triangulos rojos). Con 3 apoyos, Espacio borra los ataques.")

    def __init__(self, contexto: ContextoMinijuego) -> None:
        super().__init__(contexto)
        self.rng = random.Random(1000 + contexto.dia)
        self.carril = CARRILES // 2
        self.mensajes: list[list] = []     # [carril, altura 0..1, tipo, texto]
        self.t, self._proximo = 0.0, 0.5
        self.golpes = self.apoyos = self.borrados = 0
        self.calma = 0

    @property
    def duracion(self) -> float:
        return datos()[0]["duracion"]

    @property
    def caida(self) -> float:
        """Velocidad de caida: mas lenta con tiempo extendido, mas rapida si el lugar esta en crisis."""
        return datos()[0]["caida"] / self.contexto.ritmo

    def update(self, dt: float) -> None:
        if self.terminado:
            return
        self.t += dt
        self._proximo -= dt
        if self._proximo <= 0 and self.t < self.duracion - 1.5:
            d = datos()[0]
            tipo = APOYO if self.rng.random() < d["prob_apoyo"] else ATAQUE
            self.mensajes.append([self.rng.randrange(CARRILES), 0.0, tipo, self.rng.choice(textos()[tipo])])
            self._proximo = d["intervalo"] * self.contexto.ritmo
        quedan = []
        for m in self.mensajes:
            antes = m[1]
            m[1] += self.caida * dt
            if antes < FILA_SOFI <= m[1] and m[0] == self.carril:   # llega a la fila de Sofi en su carril
                if m[2] == APOYO:
                    self.apoyos += 1
                    self.calma = min(CALMA_LLENA, self.calma + 1)
                else:
                    self.golpes += 1
                continue
            if m[1] < 1.05:
                quedan.append(m)
        self.mensajes = quedan

    def accion(self, nombre: str) -> None:
        if self.terminado:
            return
        if nombre == "izq":
            self.carril = max(0, self.carril - 1)
        elif nombre == "der":
            self.carril = min(CARRILES - 1, self.carril + 1)
        elif nombre == "espacio" and self.calma >= CALMA_LLENA:   # la calma borra los ataques en pantalla
            ataques = [m for m in self.mensajes if m[2] == ATAQUE]
            self.borrados += len(ataques)
            self.mensajes = [m for m in self.mensajes if m[2] != ATAQUE]
            self.calma = 0

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion

    def resultado(self) -> ResultadoMinijuego:
        bien = self.apoyos + self.borrados // 2
        impacto = Impact(coexistence=bien - 2 * self.golpes, digital_wellbeing=self.apoyos - 2 * self.golpes,
                         conflicts=self.golpes // 2, score=bien - self.golpes)
        credibilidad = max(-6, min(6, (bien - 2 * self.golpes) // 2))
        if self.golpes == 0:
            texto = f"Ningun ataque llego a Sofi y atrapaste {self.apoyos} mensajes de apoyo."
        elif self.golpes > bien:
            texto = f"{self.golpes} ataques llegaron a Sofi: el acoso le gano al apoyo."
        else:
            texto = f"Atrapaste {self.apoyos} apoyos y borraste {self.borrados} ataques; {self.golpes} llegaron a Sofi."
        return ResultadoMinijuego(impacto, credibilidad, texto)

    def estado(self) -> dict:
        s = self.rng.getstate()
        return {"carril": self.carril, "mensajes": self.mensajes, "t": self.t, "proximo": self._proximo,
                "golpes": self.golpes, "apoyos": self.apoyos, "borrados": self.borrados, "calma": self.calma,
                "rng": [s[0], list(s[1]), s[2]]}

    def restaurar(self, estado: dict) -> None:
        self.carril, self.mensajes = int(estado["carril"]), [list(m) for m in estado["mensajes"]]
        self.t, self._proximo = float(estado["t"]), float(estado["proximo"])
        self.golpes, self.apoyos, self.borrados = int(estado["golpes"]), int(estado["apoyos"]), int(estado["borrados"])
        self.calma = int(estado["calma"])
        self.rng.setstate((estado["rng"][0], tuple(estado["rng"][1]), estado["rng"][2]))
