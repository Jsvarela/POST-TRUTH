from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from post_truth.models.pistas import Pista, validar_pistas
from post_truth.models.publicacion import Autor, Imagen


class Role(Enum):
    CITIZEN = "Ciudadano"
    JOURNALIST = "Periodista"
    INFLUENCER = "Influencer"
    CANDIDATE = "Candidato a alcalde"


@dataclass(frozen=True)
class Impact:
    verified_information: int = 0
    trust: int = 0
    coexistence: int = 0
    digital_wellbeing: int = 0
    misinformation: int = 0
    conflicts: int = 0
    score: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, int] | None) -> "Impact":
        if not data:
            return cls()
        return cls(
            verified_information=data.get("verified_information", 0),
            trust=data.get("trust", 0),
            coexistence=data.get("coexistence", 0),
            digital_wellbeing=data.get("digital_wellbeing", 0),
            misinformation=data.get("misinformation", 0),
            conflicts=data.get("conflicts", 0),
            score=data.get("score", 0),
        )

    def scaled_for_role(self, role: Role) -> "Impact":
        if role is Role.INFLUENCER:
            factor = 1.35
        elif role is Role.JOURNALIST:
            factor = 1.2 if self.verified_information > 0 else 0.75
        elif role is Role.CANDIDATE:
            factor = 1.25 if self.trust != 0 else 1.0
        else:
            factor = 1.0
        return Impact(
            verified_information=round(self.verified_information * factor),
            trust=round(self.trust * factor),
            coexistence=round(self.coexistence * factor),
            digital_wellbeing=round(self.digital_wellbeing * factor),
            misinformation=round(self.misinformation * factor),
            conflicts=round(self.conflicts * factor),
            score=round(self.score * factor),
        )

    def __add__(self, other: "Impact") -> "Impact":
        return Impact(
            verified_information=self.verified_information + other.verified_information,
            trust=self.trust + other.trust,
            coexistence=self.coexistence + other.coexistence,
            digital_wellbeing=self.digital_wellbeing + other.digital_wellbeing,
            misinformation=self.misinformation + other.misinformation,
            conflicts=self.conflicts + other.conflicts,
            score=self.score + other.score,
        )

    def as_lines(self) -> list[str]:
        return [
            f"Informacion verificada: {self.verified_information:+}",
            f"Confianza ciudadana: {self.trust:+}",
            f"Convivencia: {self.coexistence:+}",
            f"Bienestar digital: {self.digital_wellbeing:+}",
            f"Desinformacion: {self.misinformation:+}",
            f"Conflictos: {self.conflicts:+}",
            f"Puntaje: {self.score:+}",
        ]


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    title: str
    content: str
    kind: str
    truth_level: int
    zone: str = ""  # id de la zona de la ciudad donde ocurre (ver structures/grafo_ciudad.py)
    # Tarjeta de Civitas: quien publica, de donde sale, cuando, imagen y reacciones...
    author: Autor | None = None
    source: str = ""
    date: str = ""
    image: Imagen | None = None
    likes: int = 0
    comments: int = 0
    # ...y las pistas que se pueden investigar (una por zona de la tarjeta)
    clues: tuple[Pista, ...] = ()

    @classmethod
    def from_dict(cls, d: dict) -> "NewsEvent":
        """Lee un evento de data/events.json (los campos de la tarjeta y las pistas son opcionales)."""
        return cls(
            event_id=d["id"], title=d["title"], content=d["content"], kind=d["kind"],
            truth_level=d["truth_level"], zone=d.get("zona", ""),
            author=Autor.from_dict(d["autor"]) if d.get("autor") else None,
            source=d.get("fuente", ""), date=d.get("fecha", ""),
            image=Imagen.from_dict(d["imagen"]) if d.get("imagen") else None,
            likes=int(d.get("likes", 0)), comments=int(d.get("comentarios", 0)),
            clues=validar_pistas(Pista.from_dict(p) for p in d.get("pistas", [])))

    def to_dict(self) -> dict:
        """Mismo formato que events.json (sin las decisiones, que viven en el arbol)."""
        d: dict = {"id": self.event_id, "title": self.title, "content": self.content, "kind": self.kind,
                   "truth_level": self.truth_level, "zona": self.zone}
        if self.author is not None:
            d["autor"] = self.author.to_dict()
        d.update({"fuente": self.source, "fecha": self.date})
        if self.image is not None:
            d["imagen"] = self.image.to_dict()
        d.update({"likes": self.likes, "comentarios": self.comments, "pistas": [p.to_dict() for p in self.clues]})
        return d
