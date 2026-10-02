"""Prueba de humo del modo de sustentacion de la version Tkinter (obsoleta, tag tkinter-entrega1).

Solo comprueba que sigue funcionando despues de convertir models.py en paquete y de agregar los
campos `tipo`, `evidencias` y demas: arranca, muestra DFS y BFS y inserta/elimina una rama del arbol. Se omite
si no hay Tkinter o pantalla disponible. Ese modo cubre el arbol; los grafos se demuestran con
los fragmentos de docs/entrega2_grafos.md y con sus pruebas unitarias.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:  # pragma: no cover
    tk = None


@unittest.skipIf(tk is None, "tkinter no instalado")
class ModoSustentacionTkTest(unittest.TestCase):
    def setUp(self) -> None:
        from post_truth.app import DecisionGameApp
        try:
            self.app = DecisionGameApp()
        except tk.TclError as error:
            self.skipTest(f"sin pantalla para Tkinter: {error}")
        self.app.withdraw()
        # El panel confirma/avisa con cuadros de dialogo: se responden solos para no bloquear
        self.parches = [mock.patch.object(messagebox, nombre, return_value=True)
                        for nombre in ("askyesno", "showinfo", "showwarning", "showerror")]
        for parche in self.parches:
            parche.start()

    def tearDown(self) -> None:
        for parche in getattr(self, "parches", []):
            parche.stop()
        if hasattr(self, "app"):
            # Cancela los temporizadores `after` del panel (turnos, animaciones) para que no se
            # disparen despues de destruir la ventana y ensucien la salida de las pruebas.
            for pendiente in self.app.tk.call("after", "info"):
                self.app.after_cancel(pendiente)
            self.app.update_idletasks()   # ttk deja tareas "idle" (ThemeChanged) que fallan si la ventana ya no existe
            self.app.destroy()

    def test_dfs_y_bfs_se_muestran(self) -> None:
        self.app._show_dfs()
        self.app._show_bfs()
        self.app.update()

    def test_insertar_y_eliminar_una_rama(self) -> None:
        arbol = self.app.current_tree
        antes = len(list(arbol.dfs_nodes()))
        self.app._insert_demo()
        self.assertEqual(len(list(arbol.dfs_nodes())), antes + 1)
        self.app._delete_selected()
        self.assertEqual(len(list(arbol.dfs_nodes())), antes)

    def test_carga_todos_los_eventos_con_los_campos_nuevos(self) -> None:
        self.assertGreaterEqual(len(self.app.trees), 16)
        for arbol in self.app.trees:
            self.assertTrue(arbol.event.evidences)


if __name__ == "__main__":
    unittest.main()
