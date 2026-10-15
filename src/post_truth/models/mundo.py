"""Mundo caminable de Ciudad Nova visto desde arriba. Logica pura (sin pygame) y serializable.

El mapa ES el grafo de la ciudad: cada plaza es un vertice (un circulo) y cada calle una arista (un segmento
con ancho, una "capsula"). Solo se puede estar sobre esa union de formas, asi que cualquier angulo de calle
funciona igual (hay calles diagonales).

MOVIMIENTO: `mover(dir_x, dir_y, dt)` avanza `velocidad * dt` (pixeles del mundo por segundo) en sub-pasos fijos
de PASO segundos. Con sub-pasos fijos, 30 y 60 FPS recorren exactamente la misma secuencia de pasos: el resultado
no depende de los FPS. Si un paso cae fuera de las calles, se corrige al punto valido mas cercano: el personaje
resbala a lo largo del borde en vez de quedarse pegado.

COBRO POR CALLE (etapa M2): cada calle cuesta su distancia del grafo de la ciudad (en rayos de energia). Se cobra
al ENTRAR a una calle que no esta pagada; queda pagada hasta llegar a cualquiera de sus dos plazas, asi que dar la
vuelta a mitad de calle no cobra ni devuelve nada. Si no alcanza, la entrada a esa calle funciona como pared.
Para no cobrar dos veces por moverse justo en la boca de una calle hay histeresis: se sale de una plaza al pasar
su radio, pero se llega a ella recien al estar MARGEN_LLEGADA * radio_jugador mas adentro.

Las posiciones estan en pixeles del MUNDO (data/mundo.json), no de la pantalla: la vista las convierte.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PASO = 1 / 120   # segundos por sub-paso de movimiento
MARGEN_LLEGADA = 2   # se "llega" a una plaza al estar a radio - MARGEN_LLEGADA * radio_jugador de su centro

Punto = tuple[float, float]


@dataclass(frozen=True)
class Plaza:
    id: str
    pos: Punto
    radio: float


@dataclass(frozen=True)
class Calle:
    desde: str
    hasta: str
    ancho: float


@dataclass(frozen=True)
class Edificio:
    zona: str
    rect: tuple[float, float, float, float]   # x, y, ancho, alto
    entrada: Punto                             # donde hay que pararse para entrar (sobre la plaza)
    radio: float                               # distancia a la entrada para poder interactuar


def _cercano_en_segmento(p: Punto, a: Punto, b: Punto) -> Punto:
    """Punto del segmento ab mas cercano a p (proyeccion acotada a [0, 1])."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / largo2))
    return ax + t * dx, ay + t * dy


def _acercar(p: Punto, centro: Punto, radio: float) -> Punto:
    """p si esta a `radio` o menos de `centro`; si no, el punto a distancia `radio` en direccion a p."""
    d = math.dist(p, centro)
    if d <= radio:
        return p
    f = radio / d
    return centro[0] + (p[0] - centro[0]) * f, centro[1] + (p[1] - centro[1]) * f


class MundoCiudad:
    def __init__(self, tamano: tuple[float, float], plazas: list[Plaza], calles: list[Calle],
                 edificios: list[Edificio], aparicion: Punto, velocidad: float = 240, radio_jugador: float = 14,
                 jugador: Punto | None = None, ultima_plaza: str | None = None,
                 calles_pagadas: set[frozenset[str]] | None = None) -> None:
        self.tamano = tamano
        self.plazas = {p.id: p for p in plazas}
        self.calles = calles
        self.edificios = edificios
        self.aparicion = aparicion
        self.velocidad = velocidad
        self.radio_jugador = radio_jugador
        self._validar()
        self.jugador: Punto = jugador if jugador is not None else aparicion
        if not self.es_transitable(self.jugador):
            raise ValueError(f"El jugador no esta sobre una calle o plaza: {self.jugador}")
        # Ultima plaza a la que se llego (la sesion de la partida tiene esta misma zona) y calles ya pagadas
        self.ultima_plaza = ultima_plaza or self.plaza_en(self.jugador) or min(
            self.plazas.values(), key=lambda p: math.dist(p.pos, self.jugador)).id
        if self.ultima_plaza not in self.plazas:
            raise ValueError(f"Plaza desconocida: {self.ultima_plaza}")
        self.calles_pagadas: set[frozenset[str]] = set(calles_pagadas or ())
        self.bloqueo: Calle | None = None   # calle que no se pudo tomar por falta de energia (para avisar)

    def _validar(self) -> None:
        if self.tamano[0] <= 0 or self.tamano[1] <= 0 or self.velocidad <= 0 or self.radio_jugador <= 0:
            raise ValueError("Tamano, velocidad y radio del jugador deben ser positivos")
        for c in self.calles:
            if c.desde not in self.plazas or c.hasta not in self.plazas:
                raise ValueError(f"Calle con plaza desconocida: {c.desde} - {c.hasta}")
            if c.ancho / 2 <= self.radio_jugador:
                raise ValueError(f"La calle {c.desde} - {c.hasta} es demasiado angosta para el jugador")
        for p in self.plazas.values():
            if p.radio <= self.radio_jugador:
                raise ValueError(f"La plaza {p.id} es demasiado pequena para el jugador")
        for e in self.edificios:
            if e.zona not in self.plazas:
                raise ValueError(f"Edificio de una zona desconocida: {e.zona}")
            if not self.es_transitable(e.entrada):
                raise ValueError(f"La entrada de {e.zona} no esta sobre una calle o plaza")
        if not self.es_transitable(self.aparicion):
            raise ValueError("El punto de aparicion no esta sobre una calle o plaza")

    # --- geometria ----------------------------------------------------------------------
    def _formas(self):
        """Cada forma transitable como (centro_o_segmento, radio util para el CENTRO del jugador)."""
        r = self.radio_jugador
        for p in self.plazas.values():
            yield (p.pos, p.pos), p.radio - r
        for c in self.calles:
            yield (self.plazas[c.desde].pos, self.plazas[c.hasta].pos), c.ancho / 2 - r

    def es_transitable(self, p: Punto) -> bool:
        """El jugador (un circulo de radio_jugador centrado en p) cabe entero en alguna calle o plaza. O(V + E)."""
        return any(math.dist(p, _cercano_en_segmento(p, a, b)) <= util + 1e-9 for (a, b), util in self._formas())

    def _corregir(self, p: Punto) -> Punto:
        """El punto transitable mas cercano a p: si p ya es valido, p mismo. Es lo que produce el deslizamiento."""
        mejor, mejor_d = p, math.inf
        for (a, b), util in self._formas():
            q = _acercar(p, _cercano_en_segmento(p, a, b), util)
            d = math.dist(p, q)
            if d < mejor_d:
                mejor, mejor_d = q, d
                if d == 0:
                    break
        return mejor

    def plaza_en(self, p: Punto, margen: float = 0) -> str | None:
        """La plaza que contiene p (a `margen` o mas del borde hacia adentro), o None."""
        for pl in self.plazas.values():
            if math.dist(p, pl.pos) <= pl.radio - margen:
                return pl.id
        return None

    def calle_en(self, p: Punto) -> Calle | None:
        """La calle sobre la que esta p si no esta en una plaza (en los datos, fuera de las plazas las calles no
        se solapan; si se solaparan, gana la mas cercana)."""
        if self.plaza_en(p) is not None:
            return None
        cerca = [(math.dist(p, _cercano_en_segmento(p, self.plazas[c.desde].pos, self.plazas[c.hasta].pos)), i)
                 for i, c in enumerate(self.calles)]
        d, i = min(cerca, default=(math.inf, -1))
        return self.calles[i] if d <= self.calles[i].ancho / 2 else None

    # --- movimiento e interaccion --------------------------------------------------------
    def mover(self, dir_x: float, dir_y: float, dt: float, cobrar: Callable[[Calle], bool] | None = None,
              llegar: Callable[[str], None] | None = None) -> None:
        """Mueve al jugador en la direccion (dir_x, dir_y) durante dt segundos. La diagonal no es mas rapida.

        `cobrar(calle)` se llama al entrar a una calle no pagada y devuelve si alcanzo la energia (sin `cobrar`,
        caminar es gratis); `llegar(zona)` avisa al llegar a una plaza distinta de la ultima."""
        largo = math.hypot(dir_x, dir_y)
        if largo == 0 or dt <= 0:
            return
        ux, uy = dir_x / largo, dir_y / largo
        pasos = max(1, math.ceil(dt / PASO - 1e-9))
        h = dt / pasos
        self.bloqueo = None
        for _ in range(pasos):
            x, y = self.jugador
            nuevo = self._corregir((x + ux * self.velocidad * h, y + uy * self.velocidad * h))
            calle = self.calle_en(nuevo)
            if calle is not None:
                clave = frozenset((calle.desde, calle.hasta))
                if clave not in self.calles_pagadas:
                    if cobrar is not None and not cobrar(calle):
                        self.bloqueo = calle      # no alcanza: la calle es una pared, el jugador no avanza
                        return
                    self.calles_pagadas.add(clave)
            else:
                plaza = self.plaza_en(nuevo, MARGEN_LLEGADA * self.radio_jugador)
                if plaza is not None:
                    self.calles_pagadas.clear()   # al llegar a una plaza se acaba lo pagado
                    if plaza != self.ultima_plaza:
                        self.ultima_plaza = plaza
                        if llegar is not None:
                            llegar(plaza)
            self.jugador = nuevo

    def zona_al_alcance(self) -> str | None:
        """La zona cuyo edificio tiene la entrada a menos de su radio del jugador (la mas cercana), o None. Solo
        cuenta el lugar de la plaza a la que el jugador LLEGO, asi la zona coincide con la de la partida."""
        cerca = [(math.dist(self.jugador, e.entrada), e.zona) for e in self.edificios
                 if math.dist(self.jugador, e.entrada) <= e.radio and e.zona == self.ultima_plaza]
        return min(cerca)[1] if cerca else None

    # --- serializacion -------------------------------------------------------------------
    def to_dict(self) -> dict:
        """El mismo formato de data/mundo.json mas la posicion del jugador."""
        return {
            "tamano": list(self.tamano), "radio_jugador": self.radio_jugador, "velocidad": self.velocidad,
            "zonas": {p.id: {"pos": list(p.pos), "radio": p.radio} for p in self.plazas.values()},
            "calles": [{"desde": c.desde, "hasta": c.hasta, "ancho": c.ancho} for c in self.calles],
            "edificios": [{"zona": e.zona, "rect": list(e.rect), "entrada": list(e.entrada), "radio": e.radio}
                          for e in self.edificios],
            "aparicion": list(self.aparicion),
            "jugador": list(self.jugador),
            "ultima_plaza": self.ultima_plaza,
            "calles_pagadas": sorted(sorted(c) for c in self.calles_pagadas),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MundoCiudad":
        def punto(v) -> Punto:
            return float(v[0]), float(v[1])
        return cls(
            punto(d["tamano"]),
            [Plaza(id, punto(z["pos"]), float(z["radio"])) for id, z in d["zonas"].items()],
            [Calle(c["desde"], c["hasta"], float(c["ancho"])) for c in d["calles"]],
            [Edificio(e["zona"], tuple(float(v) for v in e["rect"]), punto(e["entrada"]), float(e["radio"]))
             for e in d.get("edificios", [])],
            punto(d["aparicion"]), float(d.get("velocidad", 240)), float(d.get("radio_jugador", 14)),
            punto(d["jugador"]) if "jugador" in d else None,
            d.get("ultima_plaza"),
            {frozenset(c) for c in d.get("calles_pagadas", [])},
        )

    @classmethod
    def cargar(cls, ruta: str | Path) -> "MundoCiudad":
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            return cls.from_dict(json.load(archivo))
