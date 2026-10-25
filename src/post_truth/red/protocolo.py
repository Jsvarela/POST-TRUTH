"""Protocolo del multijugador: mensajes JSON (UTF-8) sobre TCP, cada uno precedido por 4 bytes con su largo
(big-endian). TCP es un flujo de bytes sin bordes; el prefijo dice donde termina cada mensaje."""
from __future__ import annotations

import json
import struct

MAXIMO = 64 * 1024   # un mensaje mas largo se rechaza (nadie puede llenar la memoria del servidor)
_LARGO = struct.Struct(">I")


class MensajeInvalido(ValueError):
    """Largo fuera de rango o JSON que no es un objeto con "tipo"."""


def empaquetar(mensaje: dict) -> bytes:
    datos = json.dumps(mensaje, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(datos) > MAXIMO:
        raise MensajeInvalido(f"mensaje de {len(datos)} bytes (maximo {MAXIMO})")
    return _LARGO.pack(len(datos)) + datos


def desempaquetar(datos: bytes) -> dict:
    try:
        mensaje = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise MensajeInvalido(f"no es JSON: {e}") from None
    if not isinstance(mensaje, dict) or not isinstance(mensaje.get("tipo"), str):
        raise MensajeInvalido("falta el campo 'tipo'")
    return mensaje


class Lector:
    """Arma mensajes completos a partir de trozos de bytes como llegan del socket (partidos o pegados)."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def agregar(self, trozo: bytes) -> list[dict]:
        """Devuelve los mensajes que quedaron completos. Un mensaje bien enmarcado pero con JSON roto llega como
        {"tipo": "_invalido", "motivo": ...} (el flujo sigue sincronizado). Lanza MensajeInvalido si el largo es
        imposible: el llamador debe cerrar esa conexion."""
        self._buffer += trozo
        mensajes = []
        while len(self._buffer) >= _LARGO.size:
            (largo,) = _LARGO.unpack_from(self._buffer)
            if largo > MAXIMO:
                raise MensajeInvalido(f"largo anunciado {largo} (maximo {MAXIMO})")
            if len(self._buffer) < _LARGO.size + largo:
                break
            cuerpo = bytes(self._buffer[_LARGO.size:_LARGO.size + largo])
            del self._buffer[:_LARGO.size + largo]
            try:
                mensajes.append(desempaquetar(cuerpo))
            except MensajeInvalido as e:
                mensajes.append({"tipo": "_invalido", "motivo": str(e)})
        return mensajes
