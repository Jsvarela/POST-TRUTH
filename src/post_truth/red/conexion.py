"""Conexion del cliente con pantalla (R12): el socket vive en dos hilos (uno lee, otro escribe) y habla con el bucle
de Pygame solo por colas. El bucle nunca espera a la red: `recibir()` devuelve lo que ya llego y `enviar()` solo
encola. Hasta conectar (o fallar) tampoco se bloquea: eso tambien pasa en el hilo."""
from __future__ import annotations

import queue
import socket
import threading

from post_truth.red.protocolo import Lector, MensajeInvalido, empaquetar

CONECTANDO, CONECTADA, CERRADA = "conectando", "conectada", "cerrada"


class ConexionRed:
    def __init__(self, host: str, puerto: int, espera: float = 3.0) -> None:
        self.estado = CONECTANDO
        self.motivo = ""                                  # por que se cerro (para mostrarlo)
        self.entrada: queue.Queue[dict] = queue.Queue()   # hilo lector -> bucle
        self.salida: queue.Queue[bytes | None] = queue.Queue()   # bucle -> hilo escritor (None = terminar)
        self.sock: socket.socket | None = None
        self._hilo = threading.Thread(target=self._correr, args=(host, puerto, espera), daemon=True)
        self._hilo.start()

    @property
    def cerrada(self) -> bool:
        return self.estado == CERRADA

    def enviar(self, mensaje: dict) -> None:
        if not self.cerrada:
            self.salida.put(empaquetar(mensaje))

    def recibir(self) -> list[dict]:
        """Todo lo que llego desde la ultima vez, sin esperar."""
        mensajes = []
        while True:
            try:
                mensajes.append(self.entrada.get_nowait())
            except queue.Empty:
                return mensajes

    def cerrar(self) -> None:
        self._terminar("cerrada por el jugador")

    def _terminar(self, motivo: str) -> None:
        if self.cerrada:
            return
        self.estado, self.motivo = CERRADA, self.motivo or motivo
        self.salida.put(None)
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)   # despierta al hilo lector que espera en recv
            except OSError:
                pass
            self.sock.close()

    def _correr(self, host: str, puerto: int, espera: float) -> None:
        try:
            self.sock = socket.create_connection((host, puerto), timeout=espera)
            self.sock.settimeout(None)
        except OSError as e:
            self._terminar(f"no se pudo conectar: {e}")
            return
        if self.cerrada:   # se cancelo mientras conectaba
            self.sock.close()
            return
        self.estado = CONECTADA
        threading.Thread(target=self._escribir, daemon=True).start()
        lector = Lector()
        try:
            while True:
                datos = self.sock.recv(65536)
                if not datos:
                    break
                for m in lector.agregar(datos):
                    self.entrada.put(m)
        except (OSError, MensajeInvalido) as e:
            self.motivo = self.motivo or str(e)
        self._terminar("el servidor cerro la conexion")

    def _escribir(self) -> None:
        while True:
            datos = self.salida.get()
            if datos is None:
                return
            try:
                self.sock.sendall(datos)
            except OSError as e:
                self._terminar(f"error al enviar: {e}")
                return
