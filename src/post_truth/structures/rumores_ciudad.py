"""Rumores sobre el mapa de la ciudad: nacen en una zona y se expanden a las vecinas. Logica pura.

REGLA DE JUEGO
    Una noticia falsa que no se atiende es un rumor activo en su zona. Cada RONDA (cada vez que
    el jugador se mueve o decide) el rumor se expande un anillo: pasa a todas las zonas vecinas
    de las que ya ocupa. Cada zona infectada cuesta una penalizacion pequena por ronda, asi que
    dejar un rumor crecer sale caro. Verificar/Reportar en su zona (o "Desmentir" estando en una
    zona infectada) lo elimina.

POR QUE ASI
    Expandir "todas las vecinas de las zonas ocupadas" es avanzar un nivel de BFS desde el
    origen (el anillo k = zonas a k saltos), asi que tras k rondas el rumor ocupa exactamente lo
    que `GrafoCiudad.expuestas(origen, k)` predice. Una ronda cuesta O(suma de grados de las
    zonas ocupadas), nunca mas que O(V + E).

VISIBILIDAD
    Un rumor solo se muestra al jugador cuando ya empezo a correr (edad >= 1). Si se viera desde
    que aparece la noticia, el mapa delataria cuales publicaciones son falsas y no habria nada
    que investigar.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from post_truth.models import Impact
from post_truth.structures.grafo_ciudad import GrafoCiudad

# Costo por ronda: cada zona infectada suma 1 de desinformacion y medio de conflicto, con tope
# para que un rumor enorme no decida la partida de golpe.
TOPE_DESINFORMACION = 6
TOPE_CONFLICTOS = 4


@dataclass
class Rumor:
    id: str                                   # id del evento (noticia) del que nacio
    origen: str                               # zona donde nacio
    zonas: list[str] = field(default_factory=list)   # zonas ocupadas, en orden de contagio
    edad: int = 0                             # rondas transcurridas desde que nacio

    @property
    def visible(self) -> bool:
        return self.edad >= 1

    def to_dict(self) -> dict:
        return {"id": self.id, "origen": self.origen, "zonas": list(self.zonas), "edad": self.edad}

    @classmethod
    def from_dict(cls, d: dict) -> "Rumor":
        return cls(d["id"], d["origen"], list(d["zonas"]), int(d.get("edad", 0)))


class RumoresCiudad:
    def __init__(self, ciudad: GrafoCiudad) -> None:
        self.ciudad = ciudad
        self._rumores: dict[str, Rumor] = {}

    # --- consulta -----------------------------------------------------------------------
    def rumor(self, id: str) -> Rumor | None:
        return self._rumores.get(id)

    def activos(self) -> list[Rumor]:
        return list(self._rumores.values())

    def visibles(self) -> list[Rumor]:
        return [r for r in self._rumores.values() if r.visible]

    def zonas_infectadas(self) -> set[str]:
        """Zonas con un rumor que el jugador ya puede ver."""
        return {z for r in self.visibles() for z in r.zonas}

    def zonas_en_riesgo(self) -> set[str]:
        """Zonas a las que llegaria algun rumor visible en la proxima ronda."""
        return {z for r in self.visibles() for z in self._proximas(r)}

    def rumor_en(self, zona: str, excluir: str | None = None) -> Rumor | None:
        """Primer rumor visible que ocupa `zona` (sin contar el de id `excluir`)."""
        return next((r for r in self.visibles() if zona in r.zonas and r.id != excluir), None)

    # --- cambios ------------------------------------------------------------------------
    def nacer(self, id: str, zona: str, radio: int = 0) -> Rumor:
        """Crea el rumor en `zona`; con `radio` > 0 ya nace extendido a esos anillos (usa
        `expuestas`, el BFS por anillos del grafo de la ciudad). Si ya existe, lo devuelve."""
        if id in self._rumores:
            return self._rumores[id]
        zonas = [zona] + [z for anillo in self.ciudad.expuestas(zona, radio) for z in anillo]
        self._rumores[id] = Rumor(id, zona, zonas)
        return self._rumores[id]

    def ampliar(self, id: str, anillos: int = 1) -> list[str]:
        """Expande el rumor `anillos` niveles YA (p. ej. al Compartirlo). Devuelve zonas nuevas."""
        r = self._rumores.get(id)
        if r is None:
            return []
        nuevas: list[str] = []
        for _ in range(anillos):
            ronda = self._proximas(r)
            r.zonas += ronda
            nuevas += ronda
        return nuevas

    def avanzar_ronda(self) -> list[tuple[str, str]]:
        """Pasa una ronda: todos los rumores envejecen y se expanden un anillo. Devuelve las
        nuevas infecciones como (id_rumor, zona)."""
        nuevas: list[tuple[str, str]] = []
        for r in self._rumores.values():
            r.edad += 1
            for zona in self._proximas(r):
                r.zonas.append(zona)
                nuevas.append((r.id, zona))
        return nuevas

    def resolver(self, id: str) -> bool:
        """Elimina el rumor (verificado, reportado o desmentido). False si no existia."""
        return self._rumores.pop(id, None) is not None

    def penalizacion(self) -> Impact:
        """Costo de esta ronda por los rumores que siguen vivos y visibles."""
        n = sum(len(r.zonas) for r in self.visibles())
        if n == 0:
            return Impact()
        return Impact(misinformation=min(TOPE_DESINFORMACION, n), conflicts=min(TOPE_CONFLICTOS, n // 2))

    def _proximas(self, r: Rumor) -> list[str]:
        """Vecinas de las zonas ocupadas que aun no tienen el rumor (un anillo mas de BFS),
        sin repetir y respetando el orden de las zonas."""
        ocupadas = set(r.zonas)
        nuevas: list[str] = []
        for z in r.zonas:
            for v in self.ciudad.vecinos(z):
                if v not in ocupadas:
                    ocupadas.add(v)
                    nuevas.append(v)
        return nuevas

    # --- serializacion ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"rumores": [r.to_dict() for r in self._rumores.values()]}

    @classmethod
    def from_dict(cls, ciudad: GrafoCiudad, datos: dict) -> "RumoresCiudad":
        obj = cls(ciudad)
        for d in datos["rumores"]:
            r = Rumor.from_dict(d)
            obj._rumores[r.id] = r
        return obj
