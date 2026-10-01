"""Modelo: lo que se ve en una publicacion de Civitas (autor, avatar, imagen). Logica pura, SIN pygame.

Igual que `Personaje` y `AspectoRetrato`, solo guarda IDS (tipo de avatar, color, motivo de la
imagen), nunca colores ni superficies: la vista decide como dibujarlos con el tema activo.
"""
from __future__ import annotations

from dataclasses import dataclass

from post_truth.models.intro import AspectoRetrato, COLORES

TIPOS_AVATAR = ("retrato", "anonimo", "institucional")
# La imagen placeholder se dibuja con el fondo de una zona de la ciudad (views/zona_view.py).
MOTIVOS_IMAGEN = ("colegio", "barrio", "parque", "plaza", "alcaldia")


@dataclass(frozen=True)
class Avatar:
    """tipo "retrato": cara dibujada con `aspecto`; "anonimo": silueta sin foto (cuenta sin
    identidad); "institucional": escudo con la inicial del nombre (paginas, medios, grupos)."""
    tipo: str
    color: int = 0
    aspecto: AspectoRetrato | None = None

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_AVATAR:
            raise ValueError(f"Tipo de avatar desconocido: {self.tipo}")
        if not 0 <= self.color < COLORES:
            raise ValueError(f"Color de avatar fuera de rango: {self.color}")
        if self.tipo == "retrato" and self.aspecto is None:
            raise ValueError("Un avatar de tipo retrato necesita aspecto")

    def to_dict(self) -> dict:
        d: dict = {"tipo": self.tipo, "color": self.color}
        if self.aspecto is not None:
            a = self.aspecto
            d["aspecto"] = {"piel": a.piel, "cabello": a.cabello, "peinado": a.peinado,
                            "accesorio": a.accesorio, "color": a.color}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Avatar":
        aspecto = AspectoRetrato(**d["aspecto"]) if d.get("aspecto") else None
        return cls(d["tipo"], int(d.get("color", 0)), aspecto)


@dataclass(frozen=True)
class Autor:
    nombre: str
    avatar: Avatar

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("El autor necesita nombre")

    def to_dict(self) -> dict:
        return {"nombre": self.nombre, "avatar": self.avatar.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "Autor":
        return cls(d["nombre"], Avatar.from_dict(d["avatar"]))


@dataclass(frozen=True)
class Imagen:
    motivo: str   # una de MOTIVOS_IMAGEN
    pie: str = ""

    def __post_init__(self) -> None:
        if self.motivo not in MOTIVOS_IMAGEN:
            raise ValueError(f"Motivo de imagen desconocido: {self.motivo}")

    def to_dict(self) -> dict:
        return {"motivo": self.motivo, "pie": self.pie}

    @classmethod
    def from_dict(cls, d: dict) -> "Imagen":
        return cls(d["motivo"], d.get("pie", ""))
