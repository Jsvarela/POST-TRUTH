"""Cliente minimo del multijugador: conectar, enviar y recibir mensajes del protocolo. Lo usan las pruebas (clientes
simulados) y lo reutilizara el cliente con pantalla (R12)."""
from __future__ import annotations

import selectors
import socket
import time

from post_truth.red.protocolo import Lector, empaquetar


class ClienteRed:
    def __init__(self, host: str, puerto: int, espera: float = 3.0) -> None:
        self.sock = socket.create_connection((host, puerto), timeout=espera)
        self.sock.setblocking(False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.sock, selectors.EVENT_READ)
        self.lector = Lector()
        self.recibidos: list[dict] = []
        self.cerrado = False

    def enviar(self, mensaje: dict) -> None:
        self.enviar_bytes(empaquetar(mensaje))

    def enviar_bytes(self, datos: bytes) -> None:
        self.sock.setblocking(True)
        try:
            self.sock.sendall(datos)
        finally:
            self.sock.setblocking(False)

    def leer(self, espera: float = 0.0) -> list[dict]:
        """Lo que haya llegado (esperando como mucho `espera`); se acumula tambien en `recibidos`."""
        nuevos = []
        if self.selector.select(espera):
            try:
                datos = self.sock.recv(65536)
            except (BlockingIOError, InterruptedError):
                datos = None
            if datos == b"":
                self.cerrado = True
            elif datos:
                nuevos = self.lector.agregar(datos)
        self.recibidos += nuevos
        return nuevos

    def esperar(self, tipo: str, espera: float = 3.0, cumple=None) -> dict:
        """El primer mensaje de `tipo` (y que cumpla `cumple`, si se da) que llegue; sacandolo de `recibidos`."""
        fin = time.monotonic() + espera
        while True:
            for m in self.recibidos:
                if m["tipo"] == tipo and (cumple is None or cumple(m)):
                    self.recibidos.remove(m)
                    return m
            restante = fin - time.monotonic()
            if restante <= 0 or self.cerrado:
                raise TimeoutError(f"no llego un mensaje '{tipo}'")
            self.leer(min(0.05, restante))

    def cerrar(self) -> None:
        self.selector.close()
        self.sock.close()
        self.cerrado = True
