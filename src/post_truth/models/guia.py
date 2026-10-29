"""Mensajes guia de la primera vez (R14): una pista corta la primera vez que pasa algo. Cada mensaje sale una sola
vez por sesion de juego y se pueden apagar en Opciones. Las pantallas deciden CUANDO pasa algo; aqui solo QUE se
dice y si ya se dijo."""
from __future__ import annotations

MENSAJES = {
    "inicio": ("Bienvenida a Ciudad Nova", "Camina con WASD o flechas. El globo ! marca la noticia de hoy y G te "
                                           "guia hasta ella. F2 abre la ayuda."),
    "zona": ("Entraste a un lugar", "Pulsa E para entrar: adentro aparece sola la evidencia y eliges que hacer."),
    "transeunte": ("Alguien con un rumor", "Manten E y siguele el paso para convencerlo, o sigue de largo para "
                                          "esquivarlo. Con evidencia convences mas rapido."),
    "testigo": ("Un testigo", "Manten E a su lado para escuchar lo que vio: cuenta como evidencia."),
    "credibilidad": ("Tu credibilidad baja", "Con poca credibilidad tus desmentidos pesan menos. Verifica antes "
                                             "de compartir y no reportes sin pruebas."),
    "protesta": ("La ciudad cambia", "Una protesta cerro una calle: busca otro camino (G recalcula la ruta)."),
    "telefono": ("Frena el rumor", "Mueve el escudo (WASD o raton) sobre las bolitas rojas para atajarlas; "
                                   "Espacio lanza un desmentido en onda. Tab cambia de pestana."),
    "minijuego:chat": ("Chat del Colegio", "Ponte bajo los mensajes de apoyo (circulo) y esquiva los ataques "
                                           "(triangulo). Con 3 apoyos, Espacio borra los ataques."),
    "minijuego:mitin": ("Mitin", "Mira la forma del globo antes de responder: 1 cuadrado, 2 circulo, 3 triangulo."),
    "minijuego:rueda": ("Rueda de prensa", "Gira primero hacia quien pregunta. Si no investigaste esa prueba, "
                                           "di que no puedes afirmarlo (Espacio)."),
    "minijuego:boca": ("De boca en boca", "Ve primero a quien tiene mas vecinos. Sin evidencia, no sueltes E a medias."),
}


def mensaje(clave: str, vistas: set[str], activo: bool = True) -> tuple[str, str] | None:
    """(titulo, texto) si toca mostrarlo ahora; lo marca como visto. None si ya salio, no existe o estan apagados."""
    if not activo or clave in vistas or clave not in MENSAJES:
        return None
    vistas.add(clave)
    return MENSAJES[clave]
