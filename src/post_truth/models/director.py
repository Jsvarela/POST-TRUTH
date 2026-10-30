"""Director del dia (L1): el dia es un capitulo con pasos fijos y en orden. Logica pura y serializable.

POR QUE UNA MAQUINA DE ESTADOS LINEAL Y NO EVENTOS SUELTOS: antes el dia era un reloj donde cada cosa aparecia por
su cuenta (la crisis "entre el 20% y el 50% del dia", el fin por tiempo, el telefono y los minijuegos siempre
abiertos). Con eventos sueltos cualquier combinacion puede pasar a la vez, que es justo la sobresaturacion que se
quiere evitar, y el estado del dia queda repartido en banderas. Aqui hay UN solo estado actual (el paso) y una sola
transicion posible (al siguiente, cuando se cumple su condicion): siempre se sabe que toca, que pantallas se pueden
abrir y que falta; no hay combinaciones imposibles, se guarda en un entero y el servidor lo repite tal cual.

El director solo conoce el orden y lo permitido; las CONDICIONES y lo que pasa al entrar a cada paso las pone la
sesion (que es quien sabe si la noticia ya se decidio o si el rumor se apago).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Callable

from post_truth.config import RUTA_HISTORIA

PASOS = ("apertura", "objetivo", "noticia", "consecuencia", "minijuego", "cierre")
PANTALLAS = {   # que pantallas se pueden abrir en cada paso
    "apertura": {"mundo", "fase"},   # la pantalla de fase abre el capitulo (viene del resumen del dia anterior)
    "objetivo": {"mundo", "fase"},
    "noticia": {"mundo", "lugar", "escena", "investigacion"},
    "consecuencia": {"telefono"},
    "minijuego": {"mundo", "lugar", "minijuego"},
    "cierre": {"resumen", "fase", "resultado"},
}
DESTINO = {"apertura": "mundo", "objetivo": "mundo", "noticia": "mundo", "consecuencia": "telefono",
           "minijuego": "mundo", "cierre": "resumen"}   # a donde va el jugador si pide algo que el paso no permite
SIEMPRE = {"menu", "seleccion", "conectar", "sala", "cinematica"}   # fuera de la partida o por encima
OBJETIVOS = {"apertura": "", "objetivo": "Ir a: {lugar}", "noticia": "Investiga y decide: {lugar}",
             "consecuencia": "Frena el rumor en la red", "minijuego": "Ayuda en: {lugar}", "cierre": "Fin del dia"}
# L2: cada herramienta aparece solo en el paso donde sirve (Role.name -> paso)
HABILIDAD_EN = {"JOURNALIST": "noticia", "INFLUENCER": "consecuencia", "CANDIDATE": "minijuego", "CITIZEN": "minijuego"}
ALIADO_EN = {"JOURNALIST": "noticia", "INFLUENCER": "consecuencia", "CANDIDATE": "consecuencia",
             "CITIZEN": "consecuencia"}


@dataclass(frozen=True)
class DiaHistoria:
    noticias: tuple[str, ...]   # versiones posibles del rumor del dia (event_id); la partida sortea una
    minijuego: str              # lugar cuyo minijuego se juega ese dia
    post: bool = False                             # ese dia la historia pide crear un post (en la consecuencia)
    personajes: tuple[tuple[str, str], ...] = ()   # (id, lo que dice): ciudadanos con marca y charla
    apertura: str = ""          # cinematicas (data/cinematicas.json)
    cierre: str = ""
    pista: tuple[str, ...] = ()   # condiciones para que el dia deje su pista sobre @VerdadNova


@lru_cache(maxsize=1)
def datos() -> dict:
    with RUTA_HISTORIA.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def historia() -> tuple[DiaHistoria, ...]:
    return tuple(DiaHistoria(tuple(d["noticias"]), d["minijuego"], d.get("post", False),
                             tuple((p["id"], p.get("dice", "")) for p in d.get("personajes", ())),
                             d.get("apertura", ""), d.get("cierre", ""), tuple(d.get("pista", ())))
                 for d in datos()["dias"])


@dataclass
class DirectorDia:
    noticia: str
    zona: str
    minijuego: str
    paso: int = 0
    post: bool = False
    abierto: bool = False   # L4: ya se vio la cinematica de apertura
    cerrado: bool = False   # L4: ya se vio la de cierre

    @classmethod
    def para(cls, dia: DiaHistoria, noticia: str, zona: str) -> "DirectorDia":
        return cls(noticia, zona, dia.minijuego, post=dia.post)

    @property
    def nombre(self) -> str:
        return PASOS[self.paso]

    @property
    def fraccion(self) -> float:
        """0 al amanecer .. 1 en el cierre (el arco del sol del HUD)."""
        return self.paso / (len(PASOS) - 1)

    def permite(self, pantalla: str) -> bool:
        return pantalla in SIEMPRE or pantalla in PANTALLAS[self.nombre]

    def pantalla(self) -> str:
        return DESTINO[self.nombre]

    @property
    def destino(self) -> str | None:
        """La unica zona a la que apuntan la flecha y el globo en este paso (None: no hay que ir a ningun lado)."""
        return {"objetivo": self.zona, "noticia": self.zona, "minijuego": self.minijuego}.get(self.nombre)

    def objetivo(self, nombre_lugar: Callable[[str], str] = str) -> str:
        """Texto corto del HUD para el paso actual."""
        d = self.destino
        return OBJETIVOS[self.nombre].format(lugar=nombre_lugar(d) if d else "")

    def ofrece(self, herramienta: str, rol: str = "") -> bool:
        """"post", "aliados" (del rol `rol`) o "habilidad" (del rol `rol`): si el paso actual la pone a mano."""
        if herramienta == "post":
            return self.post and self.nombre == "consecuencia"
        tabla = HABILIDAD_EN if herramienta == "habilidad" else ALIADO_EN
        return tabla.get(rol) == self.nombre

    def avanzar(self, cumplido: Callable[[str], bool], al_entrar: Callable[[str], None]) -> list[str]:
        """Mientras el paso actual este cumplido pasa al siguiente (y avisa al entrar). El cierre no avanza solo:
        el dia siguiente lo arma la sesion. Devuelve los pasos a los que entro."""
        entrados = []
        while self.paso < len(PASOS) - 1 and cumplido(self.nombre):
            self.paso += 1
            al_entrar(self.nombre)
            entrados.append(self.nombre)
        return entrados

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DirectorDia":
        return cls(d["noticia"], d["zona"], d["minijuego"], int(d["paso"]), bool(d.get("post", False)),
                   bool(d.get("abierto", False)), bool(d.get("cerrado", False)))
