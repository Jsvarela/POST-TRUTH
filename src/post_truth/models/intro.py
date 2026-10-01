"""Modelo de la introduccion: laminas, zonas, candidatos y publicaciones. Logica pura, SIN pygame.

Todo el contenido (textos, candidatos, zonas) vive en data/intro.json; aqui solo se carga y se
valida. Igual que `Personaje`, el aspecto de un candidato son IDS (piel, cabello, peinado,
accesorio, color de campana), nunca colores ni superficies: la vista decide como dibujarlos con
el tema activo, y se podria cambiar por imagenes PNG sin tocar el modelo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MIN_LAMINAS, MAX_LAMINAS = 5, 7
TIPOS_LAMINA = ("ciudad", "zonas", "civitas", "candidatos", "cierre")
PEINADOS = ("corto", "largo", "rizado", "recogido")
ACCESORIOS = ("corbata", "aretes", "lentes", "bufanda", "barba")
TIPOS_PUBLICACION = ("rumor", "verdad")
TONOS = 2    # tonos de piel y de cabello que ofrece el tema
COLORES = 4  # colores de campana (uno por rol en el tema)


@dataclass(frozen=True)
class AspectoRetrato:
    piel: int
    cabello: int
    peinado: str
    accesorio: str
    color: int

    def __post_init__(self) -> None:
        if not (0 <= self.piel < TONOS and 0 <= self.cabello < TONOS and 0 <= self.color < COLORES):
            raise ValueError(f"Aspecto fuera de rango: {self}")
        if self.peinado not in PEINADOS:
            raise ValueError(f"Peinado desconocido: {self.peinado}")
        if self.accesorio not in ACCESORIOS:
            raise ValueError(f"Accesorio desconocido: {self.accesorio}")


@dataclass(frozen=True)
class Candidato:
    id: str
    nombre: str
    lema: str
    propuesta: str
    aspecto: AspectoRetrato


@dataclass(frozen=True)
class ZonaIntro:
    id: str
    descripcion: str


@dataclass(frozen=True)
class Publicacion:
    autor: str
    texto: str
    tipo: str          # "rumor" o "verdad"
    reacciones: int

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_PUBLICACION:
            raise ValueError(f"Tipo de publicacion desconocido: {self.tipo}")


@dataclass(frozen=True)
class Lamina:
    id: str
    tipo: str
    titulo: str
    texto: str                       # el subtitulo que se escribe letra por letra
    candidatos: tuple[str, ...] = ()  # ids de los candidatos que muestra (solo tipo "candidatos")

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_LAMINA:
            raise ValueError(f"Tipo de lamina desconocido: {self.tipo}")
        if not self.texto.strip():
            raise ValueError(f"La lamina {self.id} no tiene texto: el subtitulo siempre debe verse")


@dataclass(frozen=True)
class Intro:
    laminas: tuple[Lamina, ...]
    zonas: tuple[ZonaIntro, ...]
    candidatos: tuple[Candidato, ...]
    publicaciones: tuple[Publicacion, ...]

    def __post_init__(self) -> None:
        if not MIN_LAMINAS <= len(self.laminas) <= MAX_LAMINAS:
            raise ValueError(f"La introduccion debe tener de {MIN_LAMINAS} a {MAX_LAMINAS} laminas")
        for nombre, ids in (("laminas", [l.id for l in self.laminas]),
                            ("zonas", [z.id for z in self.zonas]),
                            ("candidatos", [c.id for c in self.candidatos])):
            if len(set(ids)) != len(ids):
                raise ValueError(f"Hay ids repetidos en {nombre}")
        conocidos = {c.id for c in self.candidatos}
        for lamina in self.laminas:
            faltan = set(lamina.candidatos) - conocidos
            if faltan:
                raise ValueError(f"La lamina {lamina.id} nombra candidatos que no existen: {sorted(faltan)}")

    def lamina(self, id: str) -> Lamina:
        return next(l for l in self.laminas if l.id == id)

    def candidato(self, id: str) -> Candidato:
        return next(c for c in self.candidatos if c.id == id)

    def zona(self, id: str) -> ZonaIntro:
        return next(z for z in self.zonas if z.id == id)

    @classmethod
    def from_dict(cls, d: dict) -> "Intro":
        return cls(
            laminas=tuple(Lamina(l["id"], l["tipo"], l["titulo"], l["texto"], tuple(l.get("candidatos", ())))
                          for l in d["laminas"]),
            zonas=tuple(ZonaIntro(z["id"], z["descripcion"]) for z in d["zonas"]),
            candidatos=tuple(Candidato(c["id"], c["nombre"], c["lema"], c["propuesta"],
                                       AspectoRetrato(**c["aspecto"])) for c in d["candidatos"]),
            publicaciones=tuple(Publicacion(p["autor"], p["texto"], p["tipo"], int(p["reacciones"]))
                                for p in d["publicaciones"]))

    def to_dict(self) -> dict:
        return {
            "laminas": [{"id": l.id, "tipo": l.tipo, "titulo": l.titulo, "texto": l.texto,
                         **({"candidatos": list(l.candidatos)} if l.candidatos else {})} for l in self.laminas],
            "zonas": [{"id": z.id, "descripcion": z.descripcion} for z in self.zonas],
            "candidatos": [{"id": c.id, "nombre": c.nombre, "lema": c.lema, "propuesta": c.propuesta,
                            "aspecto": {"piel": c.aspecto.piel, "cabello": c.aspecto.cabello,
                                        "peinado": c.aspecto.peinado, "accesorio": c.aspecto.accesorio,
                                        "color": c.aspecto.color}} for c in self.candidatos],
            "publicaciones": [{"autor": p.autor, "texto": p.texto, "tipo": p.tipo, "reacciones": p.reacciones}
                              for p in self.publicaciones],
        }

    @classmethod
    def cargar(cls, ruta: str | Path) -> "Intro":
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            return cls.from_dict(json.load(archivo))
