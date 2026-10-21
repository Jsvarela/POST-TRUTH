"""Mundo caminable de Ciudad Nova visto desde arriba."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PASO = 1 / 120
MARGEN_LLEGADA = 2

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
    peso: float | None = None


@dataclass(frozen=True)
class Edificio:
    zona: str
    rect: tuple[float, float, float, float]
    entrada: Punto
    radio: float


def _cercano_en_segmento(p: Punto, a: Punto, b: Punto) -> Punto:
    """Punto del segmento ab mas cercano a p."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / largo2))
    return ax + t * dx, ay + t * dy


def _acercar(p: Punto, centro: Punto, radio: float) -> Punto:
    """p si esta a `radio` o menos de `centro`."""
    d = math.dist(p, centro)
    if d <= radio:
        return p
    f = radio / d
    return centro[0] + (p[0] - centro[0]) * f, centro[1] + (p[1] - centro[1]) * f


class MundoCiudad:
    def __init__(self, tamano: tuple[float, float], plazas: list[Plaza], calles: list[Calle],
                 edificios: list[Edificio], aparicion: Punto, velocidad: float = 240, radio_jugador: float = 14,
                 jugador: Punto | None = None, ultima_plaza: str | None = None,
                 segundos_por_peso: float | None = None, tope_calle: float | None = None) -> None:
        self.tamano = tamano
        self.plazas = {p.id: p for p in plazas}
        self.calles = calles
        self.edificios = edificios
        self.aparicion = aparicion
        self.velocidad = velocidad
        self.radio_jugador = radio_jugador
        self.segundos_por_peso = segundos_por_peso
        self.tope_calle = tope_calle
        self._validar()
        self.jugador: Punto = jugador if jugador is not None else aparicion
        if not self.es_transitable(self.jugador):
            raise ValueError(f"El jugador no esta sobre una calle o plaza: {self.jugador}")
        self.ultima_plaza = ultima_plaza or self.plaza_en(self.jugador) or min(
            self.plazas.values(), key=lambda p: math.dist(p.pos, self.jugador)).id
        if self.ultima_plaza not in self.plazas:
            raise ValueError(f"Plaza desconocida: {self.ultima_plaza}")

    def _validar(self) -> None:
        if self.tamano[0] <= 0 or self.tamano[1] <= 0 or self.velocidad <= 0 or self.radio_jugador <= 0:
            raise ValueError("Tamano, velocidad y radio del jugador deben ser positivos")
        if self.segundos_por_peso is not None and self.segundos_por_peso <= 0:
            raise ValueError("segundos_por_peso debe ser positivo")
        if self.tope_calle is not None and self.tope_calle < 1:
            raise ValueError("tope_calle no puede frenar por debajo de la velocidad normal")
        for c in self.calles:
            if c.desde not in self.plazas or c.hasta not in self.plazas:
                raise ValueError(f"Calle con plaza desconocida: {c.desde} - {c.hasta}")
            if c.peso is not None and c.peso <= 0:
                raise ValueError(f"La calle {c.desde} - {c.hasta} necesita un peso positivo")
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

    def _formas(self):
        """Cada forma transitable como."""
        r = self.radio_jugador
        for p in self.plazas.values():
            yield (p.pos, p.pos), p.radio - r
        for c in self.calles:
            yield (self.plazas[c.desde].pos, self.plazas[c.hasta].pos), c.ancho / 2 - r

    def es_transitable(self, p: Punto) -> bool:
        """El jugador cabe entero en alguna calle o plaza."""
        return any(math.dist(p, _cercano_en_segmento(p, a, b)) <= util + 1e-9 for (a, b), util in self._formas())

    def _corregir(self, p: Punto) -> Punto:
        """El punto transitable mas cercano a p: si p ya es valido, p mismo."""
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
        """La plaza que contiene p, o None."""
        for pl in self.plazas.values():
            if math.dist(p, pl.pos) <= pl.radio - margen:
                return pl.id
        return None

    def calle_en(self, p: Punto) -> Calle | None:
        """La calle sobre la que esta p si no esta en una plaza."""
        if self.plaza_en(p) is not None:
            return None
        cerca = [(math.dist(p, _cercano_en_segmento(p, self.plazas[c.desde].pos, self.plazas[c.hasta].pos)), i)
                 for i, c in enumerate(self.calles)]
        d, i = min(cerca, default=(math.inf, -1))
        return self.calles[i] if d <= self.calles[i].ancho / 2 else None

    def velocidad_en(self, p: Punto) -> float:
        """Pixeles por segundo en p."""
        calle = self.calle_en(p)
        return self.velocidad if calle is None else self.velocidad_calle(calle)

    def _tramo(self, calle: Calle) -> float:
        a, b = self.plazas[calle.desde], self.plazas[calle.hasta]
        return math.dist(a.pos, b.pos) - a.radio - b.radio

    def velocidad_calle(self, calle: Calle) -> float:
        if calle.peso is None or self.segundos_por_peso is None:
            return self.velocidad
        v = self._tramo(calle) / (calle.peso * self.segundos_por_peso)
        return v if self.tope_calle is None else min(v, self.velocidad * self.tope_calle)

    def tiempo_calle(self, calle: Calle) -> float:
        """Segundos para ir del centro de una plaza al de la otra por esta calle."""
        a, b = self.plazas[calle.desde], self.plazas[calle.hasta]
        return self._tramo(calle) / self.velocidad_calle(calle) + (a.radio + b.radio) / self.velocidad

    def mover(self, dir_x: float, dir_y: float, dt: float, llegar: Callable[[str], None] | None = None) -> None:
        """Mueve al jugador en la direccion durante dt segundos."""
        largo = math.hypot(dir_x, dir_y)
        if largo == 0 or dt <= 0:
            return
        ux, uy = dir_x / largo, dir_y / largo
        pasos = max(1, math.ceil(dt / PASO - 1e-9))
        h = dt / pasos
        for _ in range(pasos):
            x, y = self.jugador
            v = self.velocidad_en(self.jugador)
            self.jugador = self._corregir((x + ux * v * h, y + uy * v * h))
            plaza = self.plaza_en(self.jugador, MARGEN_LLEGADA * self.radio_jugador)
            if plaza is not None and plaza != self.ultima_plaza:
                self.ultima_plaza = plaza
                if llegar is not None:
                    llegar(plaza)

    def zona_al_alcance(self) -> str | None:
        """La zona cuyo edificio tiene la entrada a menos de su radio del jugador, o None."""
        cerca = [(math.dist(self.jugador, e.entrada), e.zona) for e in self.edificios
                 if math.dist(self.jugador, e.entrada) <= e.radio and e.zona == self.ultima_plaza]
        return min(cerca)[1] if cerca else None

    def to_dict(self) -> dict:
        """El mismo formato de data/mundo.json mas la posicion del jugador."""
        return {
            "tamano": list(self.tamano), "radio_jugador": self.radio_jugador, "velocidad": self.velocidad,
            "zonas": {p.id: {"pos": list(p.pos), "radio": p.radio} for p in self.plazas.values()},
            "calles": [{"desde": c.desde, "hasta": c.hasta, "ancho": c.ancho}
                       | ({"peso": c.peso} if c.peso is not None else {}) for c in self.calles],
            "segundos_por_peso": self.segundos_por_peso, "tope_calle": self.tope_calle,
            "edificios": [{"zona": e.zona, "rect": list(e.rect), "entrada": list(e.entrada), "radio": e.radio}
                          for e in self.edificios],
            "aparicion": list(self.aparicion),
            "jugador": list(self.jugador),
            "ultima_plaza": self.ultima_plaza,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MundoCiudad":
        def punto(v) -> Punto:
            return float(v[0]), float(v[1])
        return cls(
            punto(d["tamano"]),
            [Plaza(id, punto(z["pos"]), float(z["radio"])) for id, z in d["zonas"].items()],
            [Calle(c["desde"], c["hasta"], float(c["ancho"]), c.get("peso")) for c in d["calles"]],
            [Edificio(e["zona"], tuple(float(v) for v in e["rect"]), punto(e["entrada"]), float(e["radio"]))
             for e in d.get("edificios", [])],
            punto(d["aparicion"]), float(d.get("velocidad", 240)), float(d.get("radio_jugador", 14)),
            punto(d["jugador"]) if "jugador" in d else None,
            d.get("ultima_plaza"),
            d.get("segundos_por_peso"), d.get("tope_calle"),
        )

    @classmethod
    def cargar(cls, ruta: str | Path) -> "MundoCiudad":
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            return cls.from_dict(json.load(archivo))
