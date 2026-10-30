"""Habilidades por rol y aliados de la computadora (R7). Logica pura: la sesion aplica los efectos."""
from __future__ import annotations

from dataclasses import dataclass

from post_truth.models.dominio import Impact, Role

ALIADO = "aliado"            # en `PartidaSesion.asignacion`: el rol lo juega la computadora
ENFRIAMIENTO_ALIADO = 45.0   # segundos entre pedidos de ayuda a un mismo aliado


@dataclass(frozen=True)
class Habilidad:
    nombre: str
    descripcion: str
    enfriamiento: float


HABILIDADES = {
    Role.JOURNALIST: Habilidad("Verificar a distancia", "Revela la evidencia pendiente mas cercana sin ir.", 40.0),
    Role.INFLUENCER: Habilidad("Desmentido viral", "Lanza un desmentido con el doble de fuerza.", 30.0),
    Role.CANDIDATE: Habilidad("Comunicado", "Sube la confianza y baja los conflictos.", 45.0),
    Role.CITIZEN: Habilidad("Convivencia vecinal", "Sube la convivencia y el bienestar.", 40.0),
}
AYUDAS = {   # lo que hace cada aliado cuando se le pide (politica sencilla)
    Role.JOURNALIST: "Verificar la noticia",
    Role.INFLUENCER: "Difundir tu desmentido",
    Role.CANDIDATE: "Dar un comunicado",
    Role.CITIZEN: "Reportar la cuenta del rumor",
}
MOTIVOS = {"enfriando": "Aun se esta recargando.", "nada_pendiente": "No queda nada por revisar en esta noticia.",
           "sin_rumor": "No hay un rumor corriendo ahora.", "sin_desmentido": "Primero lanza tu desmentido.",
           "no_es_aliado": "Ese rol lo juega una persona.", "no_es_su_turno": "No es tu turno.",
           "fuera_de_paso": "Ahora no: la historia te lo ofrecera en su momento."}

COMUNICADO, COMUNICADO_ALIADO = Impact(trust=4, conflicts=-3), Impact(trust=2, conflicts=-2)
CONVIVENCIA, CONVIVENCIA_ALIADO = Impact(coexistence=3, digital_wellbeing=1), Impact(coexistence=2)
DESMENTIDO_VIRAL = 2.0       # la habilidad del Influencer duplica la fuerza de su desmentido


def lupa(rol: Role) -> float:
    """Pasiva del Periodista: lupa 1.5 veces mas grande."""
    return 1.5 if rol is Role.JOURNALIST else 1.0


def mantener_lupa(rol: Role) -> float:
    """Segundos con la lupa encima para revelar: el Periodista lo nota antes."""
    return 0.6 if rol is Role.JOURNALIST else 1.0


def fuerza_desmentido(rol: Role) -> float:
    """Pasiva del Influencer: sus desmentidos llegan mas lejos."""
    return 1.5 if rol is Role.INFLUENCER else 1.0


def costo_reporte(rol: Role) -> int:
    """Pasiva del Ciudadano: reportar mal le cuesta menos credibilidad."""
    return 2 if rol is Role.CITIZEN else 5
