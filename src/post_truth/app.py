from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role


ROOT_DIR = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT_DIR / "data" / "events.json"


class DecisionGameApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("POST&TRUTH - Entrega 1")
        self.geometry("1120x720")
        self.minsize(980, 640)

        self.city = CityState()
        self.trees = load_trees(EVENTS_PATH)
        self.current_tree: DecisionTree = self.trees[0]
        self.role = tk.StringVar(value=Role.CITIZEN.value)
        self.selected_node_id: str | None = None
        self.status_text = tk.StringVar(value="Selecciona una decision para ver su impacto.")

        self._build_layout()
        self._load_tree(self.current_tree)
        self._render_city()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=12)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="POST&TRUTH", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Entrega 1: arbol n-ario de decisiones y consecuencias",
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        role_box = ttk.Combobox(
            header,
            textvariable=self.role,
            values=[role.value for role in Role],
            state="readonly",
            width=24,
        )
        role_box.grid(row=0, column=2, rowspan=2, sticky="e", padx=(16, 0))

        left = ttk.Frame(self, padding=(12, 0, 6, 12))
        left.grid(row=1, column=0, sticky="nsew")
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        event_bar = ttk.Frame(left)
        event_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        event_bar.columnconfigure(1, weight=1)
        ttk.Button(event_bar, text="Evento aleatorio", command=self._random_event).grid(
            row=0, column=0, sticky="w"
        )
        self.event_choice = ttk.Combobox(
            event_bar,
            values=[tree.event.title for tree in self.trees],
            state="readonly",
        )
        self.event_choice.current(0)
        self.event_choice.grid(row=0, column=1, sticky="ew", padx=8)
        self.event_choice.bind("<<ComboboxSelected>>", self._select_event)

        self.news_label = ttk.Label(left, wraplength=660, font=("Segoe UI", 12, "bold"))
        self.news_label.grid(row=1, column=0, sticky="ew")
        self.news_body = ttk.Label(left, wraplength=660, font=("Segoe UI", 10))
        self.news_body.grid(row=2, column=0, sticky="ew", pady=(4, 12))

        tree_frame = ttk.LabelFrame(left, text="Arbol de decisiones")
        tree_frame.grid(row=3, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree_view = ttk.Treeview(tree_frame, show="tree")
        self.tree_view.grid(row=0, column=0, sticky="nsew")
        self.tree_view.bind("<<TreeviewSelect>>", self._select_node)

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_view.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree_view.configure(yscrollcommand=yscroll.set)

        action_bar = ttk.Frame(left)
        action_bar.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(action_bar, text="Aplicar decision", command=self._apply_decision).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(action_bar, text="Insertar rama demo", command=self._insert_demo).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(action_bar, text="Eliminar rama", command=self._delete_selected).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(action_bar, text="Reiniciar ciudad", command=self._reset_city).grid(
            row=0, column=3
        )

        right = ttk.Frame(self, padding=(6, 0, 12, 12))
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        metrics = ttk.LabelFrame(right, text="Estado de Ciudad Nova")
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.columnconfigure(1, weight=1)
        self.metric_labels: dict[str, ttk.Label] = {}
        for row, (label, _value) in enumerate(self.city.as_display_rows()):
            ttk.Label(metrics, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=3)
            value_label = ttk.Label(metrics, text="")
            value_label.grid(row=row, column=1, sticky="e", padx=8, pady=3)
            self.metric_labels[label] = value_label

        impact_box = ttk.LabelFrame(right, text="Impacto de la trayectoria")
        impact_box.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.impact_text = tk.Text(impact_box, height=9, wrap="word")
        self.impact_text.grid(row=0, column=0, sticky="ew")
        self.impact_text.configure(state="disabled")

        traversal_box = ttk.LabelFrame(right, text="Recorridos del arbol")
        traversal_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(traversal_box, text="Mostrar DFS", command=self._show_dfs).grid(
            row=0, column=0, padx=8, pady=8, sticky="ew"
        )
        ttk.Button(traversal_box, text="Mostrar BFS", command=self._show_bfs).grid(
            row=0, column=1, padx=8, pady=8, sticky="ew"
        )
        traversal_box.columnconfigure(0, weight=1)
        traversal_box.columnconfigure(1, weight=1)

        log_box = ttk.LabelFrame(right, text="Explicacion y retroalimentacion")
        log_box.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        self.log = tk.Text(log_box, wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.configure(state="disabled")

        ttk.Label(self, textvariable=self.status_text, padding=(12, 4)).grid(
            row=2, column=0, columnspan=2, sticky="ew"
        )

    def _load_tree(self, tree: DecisionTree) -> None:
        self.current_tree = tree
        self.news_label.configure(
            text=f"{tree.event.title} | Tipo: {tree.event.kind} | Veracidad: {tree.event.truth_level}%"
        )
        self.news_body.configure(text=tree.event.content)
        self.tree_view.delete(*self.tree_view.get_children())
        self._insert_tree_item("", tree.root)
        self.tree_view.item(tree.root.node_id, open=True)
        self.selected_node_id = tree.root.node_id
        self.tree_view.selection_set(tree.root.node_id)
        self._write_log(
            "Arbol cargado desde JSON.\n"
            "La raiz representa la publicacion y cada hijo representa una decision posible."
        )

    def _insert_tree_item(self, parent: str, node: DecisionNode) -> None:
        self.tree_view.insert(parent, "end", iid=node.node_id, text=node.label)
        for child in node.children:
            self._insert_tree_item(node.node_id, child)

    def _select_event(self, _event: object = None) -> None:
        index = self.event_choice.current()
        self._load_tree(self.trees[index])

    def _random_event(self) -> None:
        tree = random.choice(self.trees)
        self.event_choice.set(tree.event.title)
        self._load_tree(tree)

    def _select_node(self, _event: object = None) -> None:
        selected = self.tree_view.selection()
        if not selected:
            return
        self.selected_node_id = selected[0]
        self._render_selected_impact()

    def _apply_decision(self) -> None:
        if not self.selected_node_id:
            return
        if self.selected_node_id == self.current_tree.root.node_id:
            messagebox.showinfo("Decision requerida", "Selecciona una rama de decision.")
            return
        impact = self.current_tree.accumulated_impact(self.selected_node_id)
        role = Role(self.role.get())
        scaled_impact = impact.scaled_for_role(role)
        self.city.apply(scaled_impact)
        self._render_city()
        self._write_log(
            "Decision aplicada.\n\n"
            f"Rol: {role.value}\n"
            f"Trayectoria: {self._selected_path_label()}\n\n"
            + "\n".join(scaled_impact.as_lines())
        )
        self.status_text.set("La ciudad cambio segun la trayectoria recorrida en el arbol.")

    def _insert_demo(self) -> None:
        parent_id = self.selected_node_id or self.current_tree.root.node_id
        new_id = f"{parent_id}/dialogo-comunitario"
        suffix = 2
        while self.current_tree.find(new_id) is not None:
            new_id = f"{parent_id}/dialogo-comunitario-{suffix}"
            suffix += 1
        node = self.current_tree.insert_decision(
            parent_id=parent_id,
            node_id=new_id,
            label="Dialogo comunitario",
            description="El jugador abre una conversacion respetuosa para bajar la tension.",
            impact=Impact(
                verified_information=3,
                trust=3,
                coexistence=5,
                digital_wellbeing=4,
                misinformation=-2,
                conflicts=-5,
                score=6,
            ),
        )
        self._insert_tree_item(parent_id, node)
        self.tree_view.item(parent_id, open=True)
        self.tree_view.selection_set(node.node_id)
        self.status_text.set("Insercion realizada: se agrego una nueva rama al arbol.")

    def _delete_selected(self) -> None:
        if not self.selected_node_id:
            return
        if self.selected_node_id == self.current_tree.root.node_id:
            messagebox.showwarning("No permitido", "La raiz representa la publicacion.")
            return
        removed = self.current_tree.delete_decision(self.selected_node_id)
        if removed:
            self.tree_view.delete(self.selected_node_id)
            self.selected_node_id = self.current_tree.root.node_id
            self.tree_view.selection_set(self.current_tree.root.node_id)
            self.status_text.set("Eliminacion realizada: la rama ya no participa en el arbol.")

    def _show_dfs(self) -> None:
        labels = [node.label for node in self.current_tree.dfs_nodes()]
        self._write_log(
            "Recorrido DFS (profundidad):\n"
            + " -> ".join(labels)
            + "\n\nSe usa para evaluar una trayectoria completa de consecuencias."
        )

    def _show_bfs(self) -> None:
        labels = [node.label for node in self.current_tree.bfs_nodes()]
        self._write_log(
            "Recorrido BFS (niveles):\n"
            + " -> ".join(labels)
            + "\n\nSe usa para revisar primero todas las decisiones disponibles por nivel."
        )

    def _reset_city(self) -> None:
        self.city.reset()
        self._render_city()
        self._write_log("Ciudad reiniciada a los valores iniciales de la entrega 1.")

    def _render_city(self) -> None:
        for label, value in self.city.as_display_rows():
            self.metric_labels[label].configure(text=str(value))

    def _render_selected_impact(self) -> None:
        if not self.selected_node_id:
            return
        node = self.current_tree.find(self.selected_node_id)
        if node is None:
            return
        impact = self.current_tree.accumulated_impact(self.selected_node_id)
        content = (
            f"Nodo: {node.label}\n"
            f"Descripcion: {node.description}\n\n"
            f"Trayectoria: {self._selected_path_label()}\n\n"
            + "\n".join(impact.as_lines())
        )
        self.impact_text.configure(state="normal")
        self.impact_text.delete("1.0", "end")
        self.impact_text.insert("1.0", content)
        self.impact_text.configure(state="disabled")

    def _selected_path_label(self) -> str:
        if not self.selected_node_id:
            return ""
        return " -> ".join(node.label for node in self.current_tree.path_to(self.selected_node_id))

    def _write_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", text)
        self.log.configure(state="disabled")
