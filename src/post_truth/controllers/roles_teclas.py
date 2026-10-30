"""Teclas de roles, iguales en la calle y en el telefono: H usa la habilidad; Y abre el menu de aliados y 1-3 les
pide ayuda. Desde L2 solo existen en el paso del dia que las ofrece (models/director.py): fuera de el no hacen nada."""
import pygame

from post_truth.models import roles
from post_truth.sesion import PartidaSesion

Aviso = tuple[str, str, str]   # (titulo, texto, tipo)


def tecla(s: PartidaSesion, menu: bool, key: int) -> tuple[bool, bool, Aviso | None]:
    """(la tecla era de roles, menu abierto despues, aviso a mostrar)."""
    if key == pygame.K_h and habilidad(s) is not None:
        r = s.usar_habilidad(s.jugador_actual.id)
        h = roles.HABILIDADES[s.jugador_actual.rol]
        return True, menu, (h.nombre, h.descripcion if r.ok else roles.MOTIVOS.get(r.motivo, "No se pudo."),
                            "bueno" if r.ok else "malo")
    aliados = ofrecidos(s)
    if key == pygame.K_y and aliados:
        return True, not menu, None
    if menu and key == pygame.K_ESCAPE:
        return True, False, None
    if menu and pygame.K_1 <= key < pygame.K_1 + len(aliados):
        rol = aliados[key - pygame.K_1]
        r = s.pedir_ayuda(rol)
        return True, False, (f"{rol.value} aliado", roles.AYUDAS[rol] if r.ok
                             else roles.MOTIVOS.get(r.motivo, "No se pudo."), "bueno" if r.ok else "malo")
    return False, menu, None


def ofrecidos(s: PartidaSesion) -> list:
    """Los aliados que el paso actual pone a mano."""
    d = s.director
    return [r for r in s.aliados() if d is None or d.ofrece("aliados", r.name)]


def filas_aliados(s: PartidaSesion) -> list[tuple[str, float]]:
    return [(f"{r.value} aliado: {roles.AYUDAS[r]}", s.falta(f"aliado:{r.name}")) for r in ofrecidos(s)]


def habilidad(s: PartidaSesion) -> tuple[str, float, float] | None:
    """(nombre, segundos que faltan, enfriamiento total) de la habilidad del jugador de turno; None fuera de su paso."""
    j = s.jugador_actual
    if s.director is not None and not s.director.ofrece("habilidad", j.rol.name):
        return None
    h = roles.HABILIDADES[j.rol]
    return h.nombre, s.falta(f"habilidad:{j.id}"), h.enfriamiento


def aviso_paso(s: PartidaSesion) -> Aviso | None:
    """Al entrar a un paso: que herramientas trae (la historia las presenta en su momento)."""
    partes = []
    if (h := habilidad(s)) is not None:
        partes.append(f"H: {h[0]}")
    if ofrecidos(s):
        partes.append("Y: pedir ayuda a tus aliados")
    if s.director is not None and s.director.ofrece("post"):
        partes.append("Tab: pestana Publicar")
    return ("Ahora puedes", "   ".join(partes), "info") if partes else None
