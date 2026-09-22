from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from post_truth.decision_tree import DecisionNode, DecisionTree
from post_truth.models import Impact


COLORS = {
    "bg": "#0F172A",
    "panel": "#172033",
    "panel2": "#202B40",
    "text": "#F8FAFC",
    "muted": "#A8B3C7",
    "accent": "#38BDF8",
    "good": "#34D399",
    "bad": "#FB7185",
    "line": "#334155",
}


class SustentationWindow(tk.Toplevel):

    def __init__(self, master: tk.Misc, tree: DecisionTree) -> None:
        super().__init__(master)

        self.tree = tree
        self.selected_id = tree.root.node_id

        self.title("POST-TRUTH - Modo Sustentación")
        self.geometry("1220x720")
        self.minsize(1050, 650)
        self.configure(bg=COLORS["bg"])

        self._build()
        self.after(80, self._render_tree)

    def _build(self) -> None:
        header = tk.Frame(
            self,
            bg=COLORS["bg"],
            padx=22,
            pady=16
        )
        header.pack(fill="x")

        tk.Label(
            header,
            text="MODO SUSTENTACIÓN",
            bg=COLORS["bg"],
            fg=COLORS["accent"],
            font=("Segoe UI", 22, "bold")
        ).pack(side="left")

        tk.Label(
            header,
            text=self.tree.event.title,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11)
        ).pack(side="left", padx=18)

        body = tk.Frame(
            self,
            bg=COLORS["bg"],
            padx=22
        )
        body.pack(
            fill="both",
            expand=True,
            pady=(0, 22)
        )

        body.grid_columnconfigure(0, weight=7, minsize=700)
        body.grid_columnconfigure(1, weight=3, minsize=330)
        body.grid_rowconfigure(0, weight=1)

        left = self._panel(body)
        left.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 14)
        )
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        tk.Label(
            left,
            text="Árbol de decisiones",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 15, "bold")
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 10)
        )

        tree_area = tk.Frame(
            left,
            bg=COLORS["panel"]
        )
        tree_area.grid(
            row=1,
            column=0,
            sticky="nsew"
        )
        tree_area.grid_rowconfigure(0, weight=1)
        tree_area.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            tree_area,
            bg=COLORS["panel"],
            highlightthickness=0
        )
        self.canvas.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scroll_y = tk.Scrollbar(
            tree_area,
            orient="vertical",
            command=self.canvas.yview
        )
        scroll_y.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        scroll_x = tk.Scrollbar(
            tree_area,
            orient="horizontal",
            command=self.canvas.xview
        )
        scroll_x.grid(
            row=1,
            column=0,
            sticky="ew"
        )

        self.canvas.configure(
            xscrollcommand=scroll_x.set,
            yscrollcommand=scroll_y.set
        )

        self.canvas.bind(
            "<Configure>",
            lambda _event: self._render_tree()
        )

        right = tk.Frame(
            body,
            bg=COLORS["bg"]
        )
        right.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        operations = self._panel(right)
        operations.pack(
            fill="x",
            pady=(0, 14)
        )

        tk.Label(
            operations,
            text="Operaciones",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w", pady=(0, 10))

        self._button(
            operations,
            "Recorrido DFS",
            self._show_dfs
        ).pack(fill="x", pady=4)

        self._button(
            operations,
            "Recorrido BFS",
            self._show_bfs
        ).pack(fill="x", pady=4)

        self._button(
            operations,
            "Insertar nodo demo",
            self._insert_node
        ).pack(fill="x", pady=4)

        self._button(
            operations,
            "Eliminar nodo seleccionado",
            self._delete_node,
            danger=True
        ).pack(fill="x", pady=4)

        explanation = self._panel(right)
        explanation.pack(
            fill="x",
            pady=(0, 14)
        )

        tk.Label(
            explanation,
            text="¿Qué demuestra?",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        tk.Label(
            explanation,
            text=(
                "Se utiliza un árbol n-ario porque una publicación "
                "puede producir varias decisiones y cada decisión "
                "puede generar nuevas consecuencias.\n\n"
                "Cada nodo representa una decisión o consecuencia. "
                "Las aristas representan las posibles rutas que "
                "puede seguir el jugador."
            ),
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            justify="left",
            wraplength=300,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(8, 0))

        output_panel = self._panel(right)
        output_panel.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            output_panel,
            text="Resultado",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        self.output = tk.Text(
            output_panel,
            height=10,
            wrap="word",
            bg=COLORS["panel2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 9)
        )
        self.output.pack(
            fill="both",
            expand=True,
            pady=(8, 0)
        )
        self.output.configure(state="disabled")

    def _render_tree(self) -> None:
        if not hasattr(self, "canvas"):
            return

        self.canvas.delete("all")

        levels: dict[int, list[DecisionNode]] = {}
        parents: dict[str, str] = {}

        def walk(node: DecisionNode, depth: int) -> None:
            levels.setdefault(depth, []).append(node)

            for child in node.children:
                parents[child.node_id] = node.node_id
                walk(child, depth + 1)

        walk(self.tree.root, 0)

        if not levels:
            return

        max_nodes = max(len(nodes) for nodes in levels.values())

        visible_width = max(self.canvas.winfo_width(), 650)

        virtual_width = max(
            visible_width,
            max_nodes * 155 + 80
        )

        virtual_height = max(
            self.canvas.winfo_height(),
            len(levels) * 145 + 80
        )

        self.canvas.configure(
            scrollregion=(0, 0, virtual_width, virtual_height)
        )

        positions: dict[str, tuple[float, float]] = {}

        for depth, nodes in levels.items():
            gap = virtual_width / (len(nodes) + 1)
            y = 65 + depth * 145

            for index, node in enumerate(nodes, start=1):
                positions[node.node_id] = (
                    gap * index,
                    y
                )

        for child_id, parent_id in parents.items():
            x1, y1 = positions[parent_id]
            x2, y2 = positions[child_id]

            self.canvas.create_line(
                x1,
                y1 + 30,
                x2,
                y2 - 30,
                fill=COLORS["line"],
                width=3
            )

        for nodes in levels.values():
            for node in nodes:
                x, y = positions[node.node_id]

                selected = node.node_id == self.selected_id

                fill = (
                    COLORS["accent"]
                    if selected
                    else COLORS["panel2"]
                )

                text_color = (
                    "#07111C"
                    if selected
                    else COLORS["text"]
                )

                tag = "node:" + node.node_id

                self.canvas.create_rectangle(
                    x - 68,
                    y - 30,
                    x + 68,
                    y + 30,
                    fill=fill,
                    outline=COLORS["line"],
                    width=2,
                    tags=(tag,)
                )

                self.canvas.create_text(
                    x,
                    y,
                    text=node.label,
                    fill=text_color,
                    width=120,
                    justify="center",
                    font=("Segoe UI", 8, "bold"),
                    tags=(tag,)
                )

                self.canvas.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda _event,
                    node_id=node.node_id:
                    self._select_node(node_id)
                )

    def _select_node(self, node_id: str) -> None:
        self.selected_id = node_id

        node = self.tree.find(node_id)

        if node is not None:
            self._write(
                f"Nodo seleccionado:\n"
                f"{node.label}\n\n"
                f"{node.description}"
            )

        self._render_tree()

    def _show_dfs(self) -> None:
        labels = [
            node.label
            for node in self.tree.dfs_nodes()
        ]

        self._write(
            "RECORRIDO DFS\n\n"
            + " → ".join(labels)
            + "\n\n"
            "DFS profundiza por una rama "
            "antes de regresar a explorar otra."
        )

    def _show_bfs(self) -> None:
        labels = [
            node.label
            for node in self.tree.bfs_nodes()
        ]

        self._write(
            "RECORRIDO BFS\n\n"
            + " → ".join(labels)
            + "\n\n"
            "BFS recorre el árbol por niveles, "
            "desde las decisiones inmediatas "
            "hasta las consecuencias posteriores."
        )

    def _insert_node(self) -> None:
        parent = self.tree.find(self.selected_id)

        if parent is None:
            return

        number = 1

        while True:
            new_id = f"{parent.node_id}/demo-{number}"

            if self.tree.find(new_id) is None:
                break

            number += 1

        new_node = self.tree.insert_decision(
            parent_id=parent.node_id,
            node_id=new_id,
            label="Diálogo comunitario",
            description=(
                "Nueva consecuencia agregada "
                "durante la demostración."
            ),
            impact=Impact(
                trust=2,
                coexistence=3,
                misinformation=-1,
                conflicts=-2,
                score=3
            )
        )

        self.selected_id = new_node.node_id

        self._write(
            "INSERCIÓN\n\n"
            f"Se insertó '{new_node.label}' "
            f"como hijo de '{parent.label}'."
        )

        self._render_tree()

    def _delete_node(self) -> None:
        if self.selected_id == self.tree.root.node_id:
            messagebox.showwarning(
                "No permitido",
                "La raíz representa la publicación "
                "y no puede eliminarse."
            )
            return

        node = self.tree.find(self.selected_id)

        if node is None:
            return

        label = node.label

        removed = self.tree.delete_decision(
            self.selected_id
        )

        if removed:
            self.selected_id = self.tree.root.node_id

            self._write(
                "ELIMINACIÓN\n\n"
                f"Se eliminó el nodo '{label}' "
                "y su rama."
            )

            self._render_tree()

    def _write(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    @staticmethod
    def _panel(parent: tk.Widget) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=COLORS["panel"],
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground=COLORS["line"]
        )

    @staticmethod
    def _button(
        parent: tk.Widget,
        text: str,
        command,
        danger: bool = False
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=(
                COLORS["bad"]
                if danger
                else COLORS["panel2"]
            ),
            fg=COLORS["text"],
            activebackground=COLORS["accent"],
            activeforeground="#07111C",
            relief="flat",
            bd=0,
            padx=12,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
