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

BASE_COLORS = {
    "bg": "#EEF3F2",
    "surface": "#FFFFFF",
    "surface_alt": "#F7FAF8",
    "ink": "#18222D",
    "muted": "#667085",
    "line": "#D8E2DF",
    "teal": "#0F8B8D",
    "coral": "#D95D39",
    "yellow": "#F2B84B",
    "green": "#2E7D5E",
    "red": "#B23A48",
    "dark": "#1F2933",
}

CONTRAST_COLORS = {
    "bg": "#101010",
    "surface": "#1C1C1C",
    "surface_alt": "#252525",
    "ink": "#F6F6F6",
    "muted": "#D0D0D0",
    "line": "#FFFFFF",
    "teal": "#00D4FF",
    "coral": "#FFB000",
    "yellow": "#FFE066",
    "green": "#83F28F",
    "red": "#FF5C77",
    "dark": "#F6F6F6",
}

ROLE_HELP = {
    Role.CITIZEN.value: "Equilibra bienestar y convivencia. Sus decisiones son estables.",
    Role.JOURNALIST.value: "Potencia la verificacion y reduce el dano de rumores.",
    Role.INFLUENCER.value: "Amplifica mucho el impacto, para bien o para mal.",
    Role.CANDIDATE.value: "Sus acciones pesan mas sobre la confianza ciudadana.",
}


class DecisionGameApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("POST-TRUTH - Ciudad Nova")
        self.geometry("1240x760")
        self.minsize(1120, 700)

        self.city = CityState()
        self.trees = load_trees(EVENTS_PATH)
        self.current_tree: DecisionTree = self.trees[0]
        self.role = tk.StringVar(value=Role.CITIZEN.value)
        self.status_text = tk.StringVar(value="Elige una respuesta para la publicacion actual.")
        self.timer_text = tk.StringVar(value="20 s")
        self.selected_node_id: str | None = None
        self.history: list[str] = []
        self.high_contrast = False
        self.colors = BASE_COLORS
        self.timer_after_id: str | None = None
        self.remaining_seconds = 20

        self.metric_widgets: dict[str, tuple[tk.Label, tk.Canvas]] = {}
        self.action_cards: dict[str, tk.Frame] = {}
        self.action_container: tk.Frame | None = None
        self.city_canvas: tk.Canvas | None = None
        self.tree_canvas: tk.Canvas | None = None
        self.timer_canvas: tk.Canvas | None = None
        self.preview_body: tk.Label | None = None
        self.history_box: tk.Text | None = None
        self.role_help_label: tk.Label | None = None
        self.news_title: tk.Label | None = None
        self.news_body: tk.Label | None = None
        self.news_badge: tk.Label | None = None
        self.event_choice: ttk.Combobox | None = None

        self._configure_style()
        self._build_layout()
        self._load_tree(self.current_tree, restart_timer=True)

    def _configure_style(self) -> None:
        self.configure(bg=self.colors["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["surface"],
            background=self.colors["surface"],
            foreground=self.colors["ink"],
            arrowcolor=self.colors["teal"],
            bordercolor=self.colors["line"],
            lightcolor=self.colors["line"],
            darkcolor=self.colors["line"],
            padding=6,
        )

    def _build_layout(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        self.configure(bg=self.colors["bg"])
        self.grid_columnconfigure(0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=335)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_center()
        self._build_right_panel()

        status = tk.Label(
            self,
            textvariable=self.status_text,
            bg=self.colors["dark"],
            fg="#FFFFFF" if not self.high_contrast else "#101010",
            anchor="w",
            padx=16,
            pady=7,
            font=("Segoe UI", 10, "bold"),
        )
        status.grid(row=2, column=0, columnspan=3, sticky="ew")

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=self.colors["bg"], padx=18, pady=14)
        header.grid(row=0, column=0, columnspan=3, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        title = tk.Label(
            header,
            text="POST-TRUTH",
            bg=self.colors["bg"],
            fg=self.colors["ink"],
            font=("Segoe UI", 23, "bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = tk.Label(
            header,
            text="Simulador de decisiones en Civitas | Entrega 1: arboles",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        subtitle.grid(row=1, column=0, sticky="w")

        role_frame = tk.Frame(header, bg=self.colors["bg"])
        role_frame.grid(row=0, column=2, rowspan=2, sticky="e")

        tk.Label(
            role_frame,
            text="Rol",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w")

        role_box = ttk.Combobox(
            role_frame,
            textvariable=self.role,
            values=[role.value for role in Role],
            state="readonly",
            width=24,
        )
        role_box.grid(row=1, column=0, padx=(0, 10))
        role_box.bind("<<ComboboxSelected>>", self._role_changed)

        self._button(role_frame, "Ayuda", self._open_help, style="quiet").grid(
            row=1, column=1, padx=(0, 8)
        )
        self._button(
            role_frame,
            "Alto contraste",
            self._toggle_contrast,
            style="quiet",
        ).grid(row=1, column=2)

    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self, bg=self.colors["bg"], padx=14, pady=4)
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(3, weight=1)

        timer_panel = self._panel(sidebar)
        timer_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        timer_panel.grid_columnconfigure(0, weight=1)

        tk.Label(
            timer_panel,
            text="Turno actual",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            timer_panel,
            textvariable=self.timer_text,
            bg=self.colors["surface"],
            fg=self.colors["coral"],
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=1, sticky="e")

        self.timer_canvas = tk.Canvas(
            timer_panel,
            width=212,
            height=12,
            bg=self.colors["surface"],
            highlightthickness=0,
        )
        self.timer_canvas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 10))

        self.role_help_label = tk.Label(
            timer_panel,
            text=ROLE_HELP[self.role.get()],
            wraplength=215,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        )
        self.role_help_label.grid(row=2, column=0, columnspan=2, sticky="ew")

        feed_panel = self._panel(sidebar)
        feed_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        feed_panel.grid_columnconfigure(0, weight=1)

        tk.Label(
            feed_panel,
            text="Publicaciones",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.event_choice = ttk.Combobox(
            feed_panel,
            values=[tree.event.title for tree in self.trees],
            state="readonly",
        )
        self.event_choice.current(0)
        self.event_choice.grid(row=1, column=0, sticky="ew")
        self.event_choice.bind("<<ComboboxSelected>>", self._select_event)

        self._button(feed_panel, "Sacar publicacion aleatoria", self._random_event).grid(
            row=2, column=0, sticky="ew", pady=(9, 0)
        )

        tools_panel = self._panel(sidebar)
        tools_panel.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        tools_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            tools_panel,
            text="Modo sustentacion",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        for row, (text, command) in enumerate(
            [
                ("Recorrido DFS", self._show_dfs),
                ("Recorrido BFS", self._show_bfs),
                ("Insertar rama demo", self._insert_demo),
                ("Eliminar decision", self._delete_selected),
            ],
            start=1,
        ):
            self._button(tools_panel, text, command, style="quiet").grid(
                row=row, column=0, sticky="ew", pady=3
            )

        note_panel = self._panel(sidebar)
        note_panel.grid(row=3, column=0, sticky="nsew")
        note_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            note_panel,
            text="Que se esta evaluando",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            note_panel,
            text=(
                "El arbol decide consecuencias. Cada ruta suma impactos y cambia "
                "los indicadores de la ciudad. DFS/BFS se muestran para sustentar "
                "la estructura sin romper la experiencia del juego."
            ),
            wraplength=215,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))

    def _build_center(self) -> None:
        center = tk.Frame(self, bg=self.colors["bg"], padx=4, pady=4)
        center.grid(row=1, column=1, sticky="nsew")
        center.grid_rowconfigure(1, weight=1)
        center.grid_rowconfigure(2, weight=1)
        center.grid_columnconfigure(0, weight=1)

        post = self._panel(center, padx=18, pady=16)
        post.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        post.grid_columnconfigure(0, weight=1)

        top_line = tk.Frame(post, bg=self.colors["surface"])
        top_line.grid(row=0, column=0, sticky="ew")
        top_line.grid_columnconfigure(0, weight=1)

        tk.Label(
            top_line,
            text="@CivitasNova",
            bg=self.colors["surface"],
            fg=self.colors["teal"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.news_badge = tk.Label(
            top_line,
            text="",
            bg=self.colors["surface_alt"],
            fg=self.colors["ink"],
            padx=8,
            pady=3,
            font=("Segoe UI", 9, "bold"),
        )
        self.news_badge.grid(row=0, column=1, sticky="e")

        self.news_title = tk.Label(
            post,
            text="",
            wraplength=560,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 17, "bold"),
        )
        self.news_title.grid(row=1, column=0, sticky="ew", pady=(10, 4))

        self.news_body = tk.Label(
            post,
            text="",
            wraplength=650,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["dark"],
            font=("Segoe UI", 11),
        )
        self.news_body.grid(row=2, column=0, sticky="ew")

        action_panel = self._panel(center, padx=18, pady=16)
        action_panel.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        action_panel.grid_columnconfigure(0, weight=1)
        action_panel.grid_rowconfigure(1, weight=1)

        action_header = tk.Frame(action_panel, bg=self.colors["surface"])
        action_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        action_header.grid_columnconfigure(0, weight=1)
        tk.Label(
            action_header,
            text="Rutas de decision",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self._button(action_header, "Confirmar decision", self._apply_decision).grid(
            row=0, column=1, sticky="e"
        )

        self.action_container = tk.Frame(action_panel, bg=self.colors["surface"])
        self.action_container.grid(row=1, column=0, sticky="nsew")
        self.action_container.grid_columnconfigure(0, weight=1)
        self.action_container.grid_columnconfigure(1, weight=1)

        tree_panel = self._panel(center, padx=18, pady=14)
        tree_panel.grid(row=2, column=0, sticky="nsew")
        tree_panel.grid_rowconfigure(1, weight=1)
        tree_panel.grid_columnconfigure(0, weight=1)

        tk.Label(
            tree_panel,
            text="Mapa visual del arbol",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.tree_canvas = tk.Canvas(
            tree_panel,
            height=230,
            bg=self.colors["surface"],
            highlightthickness=0,
        )
        self.tree_canvas.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.tree_canvas.bind("<Configure>", lambda _event: self._render_tree_map())

    def _build_right_panel(self) -> None:
        right = tk.Frame(self, bg=self.colors["bg"], padx=14, pady=4)
        right.grid(row=1, column=2, sticky="nsew")
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        city_panel = self._panel(right)
        city_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        city_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            city_panel,
            text="Ciudad Nova",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.city_canvas = tk.Canvas(
            city_panel,
            width=285,
            height=180,
            bg=self.colors["surface"],
            highlightthickness=0,
        )
        self.city_canvas.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        metrics = self._panel(right)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        metrics.grid_columnconfigure(0, weight=1)
        tk.Label(
            metrics,
            text="Indicadores",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.metric_widgets = {}
        for row, (label, _value) in enumerate(self.city.as_display_rows(), start=1):
            row_frame = tk.Frame(metrics, bg=self.colors["surface"])
            row_frame.grid(row=row, column=0, sticky="ew", pady=3)
            row_frame.grid_columnconfigure(0, weight=1)
            tk.Label(
                row_frame,
                text=label,
                bg=self.colors["surface"],
                fg=self.colors["muted"],
                font=("Segoe UI", 9),
            ).grid(row=0, column=0, sticky="w")
            value_label = tk.Label(
                row_frame,
                text="0",
                bg=self.colors["surface"],
                fg=self.colors["ink"],
                font=("Segoe UI", 9, "bold"),
            )
            value_label.grid(row=0, column=1, sticky="e")
            bar = tk.Canvas(
                row_frame,
                width=280,
                height=9,
                bg=self.colors["surface"],
                highlightthickness=0,
            )
            bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
            self.metric_widgets[label] = (value_label, bar)

        preview = self._panel(right)
        preview.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        preview.grid_columnconfigure(0, weight=1)
        tk.Label(
            preview,
            text="Impacto esperado",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.preview_body = tk.Label(
            preview,
            text="Selecciona una decision para ver la ruta y sus efectos.",
            wraplength=285,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        )
        self.preview_body.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        history_panel = self._panel(right)
        history_panel.grid(row=3, column=0, sticky="nsew")
        history_panel.grid_rowconfigure(1, weight=1)
        history_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            history_panel,
            text="Bitacora",
            bg=self.colors["surface"],
            fg=self.colors["ink"],
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.history_box = tk.Text(
            history_panel,
            height=8,
            wrap="word",
            bd=0,
            padx=8,
            pady=8,
            bg=self.colors["surface_alt"],
            fg=self.colors["ink"],
            font=("Segoe UI", 9),
        )
        self.history_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.history_box.configure(state="disabled")

    def _load_tree(
        self,
        tree: DecisionTree,
        restart_timer: bool = False,
        log_event: bool = True,
    ) -> None:
        self.current_tree = tree
        decisions = self._decision_nodes()
        self.selected_node_id = decisions[0].node_id if decisions else None

        if self.event_choice is not None:
            self.event_choice.set(tree.event.title)
        if self.news_title is not None:
            self.news_title.configure(text=tree.event.title)
        if self.news_body is not None:
            self.news_body.configure(text=tree.event.content)
        if self.news_badge is not None:
            self.news_badge.configure(text=self._event_badge_text(tree))

        self._render_actions()
        self._render_preview()
        self._render_city()
        self._render_tree_map()
        if log_event:
            self._append_history(f"Nueva publicacion: {tree.event.title}")
        self.status_text.set("La publicacion esta activa. Escoge una respuesta.")

        if restart_timer:
            self._restart_timer()

    def _render_actions(self) -> None:
        if self.action_container is None:
            return
        for child in self.action_container.winfo_children():
            child.destroy()
        self.action_cards = {}

        decisions = self._decision_nodes()
        for index, node in enumerate(decisions):
            row = index // 2
            column = index % 2
            card = self._decision_card(self.action_container, node)
            card.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
            self.action_container.grid_rowconfigure(row, weight=1)
            self.action_cards[node.node_id] = card

    def _decision_card(self, parent: tk.Widget, node: DecisionNode) -> tk.Frame:
        selected = node.node_id == self.selected_node_id
        bg = self.colors["surface_alt"] if not selected else "#E6F4F1"
        if self.high_contrast and selected:
            bg = "#04333A"
        border = self.colors["teal"] if selected else self.colors["line"]

        card = tk.Frame(
            parent,
            bg=bg,
            padx=12,
            pady=10,
            highlightthickness=2 if selected else 1,
            highlightbackground=border,
        )
        card.grid_columnconfigure(0, weight=1)

        tk.Label(
            card,
            text=node.label,
            bg=bg,
            fg=self.colors["ink"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            card,
            text=node.description,
            bg=bg,
            fg=self.colors["muted"],
            wraplength=275,
            justify="left",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="ew", pady=(5, 8))

        route = " > ".join(path_node.label for path_node in self.current_tree.path_to(node.node_id)[1:])
        tk.Label(
            card,
            text=f"Ruta: {route}",
            bg=bg,
            fg=self.colors["teal"] if not self.high_contrast else self.colors["yellow"],
            wraplength=275,
            justify="left",
            font=("Segoe UI", 8, "bold"),
        ).grid(row=2, column=0, sticky="ew")

        impact = self.current_tree.accumulated_impact(node.node_id).scaled_for_role(
            Role(self.role.get())
        )
        summary = self._impact_summary(impact)
        tk.Label(
            card,
            text=summary,
            bg=bg,
            fg=self.colors["dark"],
            wraplength=275,
            justify="left",
            font=("Segoe UI", 8),
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        button_text = "Seleccionada" if selected else "Elegir esta respuesta"
        self._button(
            card,
            button_text,
            lambda node_id=node.node_id: self._choose_node(node_id),
            style="primary" if selected else "quiet",
        ).grid(row=4, column=0, sticky="ew", pady=(9, 0))

        return card

    def _choose_node(self, node_id: str) -> None:
        self.selected_node_id = node_id
        self._render_actions()
        self._render_preview()
        self._render_tree_map()
        node = self.current_tree.find(node_id)
        if node:
            self.status_text.set(f"Decision seleccionada: {node.label}")

    def _apply_decision(self) -> None:
        if not self.selected_node_id:
            messagebox.showinfo("Decision requerida", "Selecciona una decision primero.")
            return

        node = self.current_tree.find(self.selected_node_id)
        if node is None:
            return

        impact = self.current_tree.accumulated_impact(self.selected_node_id)
        scaled_impact = impact.scaled_for_role(Role(self.role.get()))
        self.city.apply(scaled_impact)
        self._render_city()

        feedback = self._feedback_for(scaled_impact)
        self._append_history(
            f"{node.label}: {feedback}\n"
            f"Ruta: {self._selected_path_label()}\n"
            f"{self._impact_summary(scaled_impact)}"
        )
        self._random_event(restart_timer=True, announce=False)
        self.status_text.set(f"{feedback} Nueva publicacion en Civitas.")

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
            description="Abres una conversacion respetuosa para bajar la tension.",
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
        self.selected_node_id = node.node_id
        self._render_actions()
        self._render_preview()
        self._render_tree_map()
        self._append_history("Insercion: se agrego una nueva rama al arbol.")
        self.status_text.set("Rama agregada. Ahora esa consecuencia participa en DFS/BFS.")

    def _delete_selected(self) -> None:
        if not self.selected_node_id:
            return
        node = self.current_tree.find(self.selected_node_id)
        if node is None:
            return
        if node.node_id == self.current_tree.root.node_id:
            messagebox.showwarning("No permitido", "La raiz representa la publicacion.")
            return
        removed = self.current_tree.delete_decision(node.node_id)
        if removed:
            decisions = self._decision_nodes()
            self.selected_node_id = decisions[0].node_id if decisions else None
            self._render_actions()
            self._render_preview()
            self._render_tree_map()
            self._append_history(f"Eliminacion: se retiro la decision '{node.label}'.")
            self.status_text.set("Rama eliminada del arbol de decisiones.")

    def _show_dfs(self) -> None:
        labels = [node.label for node in self.current_tree.dfs_nodes()]
        self._append_history(
            "DFS: "
            + " -> ".join(labels)
            + "\nUso: evaluar una ruta completa antes de volver a otra rama."
        )
        self.status_text.set("DFS mostrado en la bitacora.")

    def _show_bfs(self) -> None:
        labels = [node.label for node in self.current_tree.bfs_nodes()]
        self._append_history(
            "BFS: "
            + " -> ".join(labels)
            + "\nUso: revisar decisiones por niveles, de lo inmediato a lo secundario."
        )
        self.status_text.set("BFS mostrado en la bitacora.")

    def _select_event(self, _event: object = None) -> None:
        if self.event_choice is None:
            return
        index = self.event_choice.current()
        self._load_tree(self.trees[index], restart_timer=True)

    def _random_event(self, restart_timer: bool = True, announce: bool = True) -> None:
        tree = random.choice(self.trees)
        if len(self.trees) > 1:
            while tree is self.current_tree:
                tree = random.choice(self.trees)
        self._load_tree(tree, restart_timer=restart_timer)
        if announce:
            self.status_text.set("Nueva publicacion aleatoria en Civitas.")

    def _role_changed(self, _event: object = None) -> None:
        if self.role_help_label is not None:
            self.role_help_label.configure(text=ROLE_HELP[self.role.get()])
        self._render_actions()
        self._render_preview()
        self.status_text.set(f"Rol activo: {self.role.get()}")

    def _restart_timer(self) -> None:
        if self.timer_after_id is not None:
            self.after_cancel(self.timer_after_id)
        self.remaining_seconds = 20
        self._tick_timer()

    def _tick_timer(self) -> None:
        self.timer_text.set(f"{self.remaining_seconds} s")
        self._draw_timer()
        if self.remaining_seconds == 0:
            self.status_text.set("Tiempo agotado. Puedes decidir, pero la ciudad ya esta reaccionando.")
            return
        self.remaining_seconds -= 1
        self.timer_after_id = self.after(1000, self._tick_timer)

    def _draw_timer(self) -> None:
        if self.timer_canvas is None:
            return
        self.timer_canvas.delete("all")
        width = 212
        height = 10
        percent = max(0, self.remaining_seconds) / 20
        color = self.colors["green"] if percent > 0.5 else self.colors["yellow"]
        if percent <= 0.25:
            color = self.colors["coral"]
        self.timer_canvas.create_rectangle(0, 2, width, height, fill=self.colors["line"], outline="")
        self.timer_canvas.create_rectangle(0, 2, width * percent, height, fill=color, outline="")

    def _render_city(self) -> None:
        for label, value in self.city.as_display_rows():
            value_label, bar = self.metric_widgets[label]
            value_label.configure(text=str(value))
            self._draw_metric_bar(bar, label, value)
        self._render_city_map()

    def _draw_metric_bar(self, bar: tk.Canvas, label: str, value: int) -> None:
        bar.delete("all")
        width = 280
        height = 9
        if label == "Puntaje jugador":
            percent = max(0, min(100, value + 50))
        else:
            percent = value

        is_risk = label in {"Desinformacion", "Conflictos"}
        if is_risk:
            color = self.colors["green"] if percent < 35 else self.colors["yellow"]
            if percent > 65:
                color = self.colors["red"]
        else:
            color = self.colors["red"] if percent < 35 else self.colors["yellow"]
            if percent > 65:
                color = self.colors["green"]
        bar.create_rectangle(0, 0, width, height, fill=self.colors["line"], outline="")
        bar.create_rectangle(0, 0, width * (percent / 100), height, fill=color, outline="")

    def _render_city_map(self) -> None:
        if self.city_canvas is None:
            return
        canvas = self.city_canvas
        canvas.delete("all")
        health = self._city_health()
        if health >= 70:
            mood_color = self.colors["green"]
            mood = "Ciudad estable"
        elif health >= 45:
            mood_color = self.colors["yellow"]
            mood = "Ciudad en tension"
        else:
            mood_color = self.colors["red"]
            mood = "Crisis digital"

        roads = [
            ((70, 62), (142, 88)),
            ((142, 88), (220, 54)),
            ((142, 88), (210, 135)),
            ((142, 88), (64, 136)),
        ]
        for start, end in roads:
            canvas.create_line(*start, *end, fill=self.colors["line"], width=5)
            canvas.create_line(*start, *end, fill=self.colors["muted"], width=1)

        districts = [
            ("Colegio", 28, 34, 112, 88, self.colors["teal"]),
            ("Plaza", 178, 28, 260, 82, self.colors["coral"]),
            ("Barrio", 102, 68, 182, 122, mood_color),
            ("Parque", 24, 116, 112, 166, self.colors["green"]),
            ("Alcaldia", 168, 112, 270, 166, self.colors["yellow"]),
        ]
        for name, x1, y1, x2, y2, color in districts:
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=name,
                fill="#FFFFFF" if name != "Alcaldia" else "#18222D",
                font=("Segoe UI", 9, "bold"),
            )

        canvas.create_text(
            142,
            12,
            text=f"{mood} | salud {health}%",
            fill=self.colors["ink"],
            font=("Segoe UI", 10, "bold"),
        )

    def _render_preview(self) -> None:
        if self.preview_body is None:
            return
        if not self.selected_node_id:
            self.preview_body.configure(text="Selecciona una decision para ver la ruta y sus efectos.")
            return

        node = self.current_tree.find(self.selected_node_id)
        if node is None:
            return
        impact = self.current_tree.accumulated_impact(node.node_id).scaled_for_role(
            Role(self.role.get())
        )
        self.preview_body.configure(
            text=(
                f"Decision: {node.label}\n"
                f"Ruta: {self._selected_path_label()}\n\n"
                f"{self._impact_summary(impact)}\n\n"
                f"{node.description}"
            )
        )

    def _render_tree_map(self) -> None:
        if self.tree_canvas is None:
            return
        canvas = self.tree_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 580)
        levels: dict[int, list[DecisionNode]] = {}
        parents: dict[str, str] = {}

        def walk(node: DecisionNode, depth: int) -> None:
            levels.setdefault(depth, []).append(node)
            for child in node.children:
                parents[child.node_id] = node.node_id
                walk(child, depth + 1)

        walk(self.current_tree.root, 0)
        positions: dict[str, tuple[float, float]] = {}
        for depth, nodes in levels.items():
            y = 32 + depth * 82
            gap = width / (len(nodes) + 1)
            for index, node in enumerate(nodes, start=1):
                positions[node.node_id] = (gap * index, y)

        selected_path = (
            {node.node_id for node in self.current_tree.path_to(self.selected_node_id)}
            if self.selected_node_id
            else set()
        )

        for child_id, parent_id in parents.items():
            x1, y1 = positions[parent_id]
            x2, y2 = positions[child_id]
            color = self.colors["teal"] if child_id in selected_path else self.colors["line"]
            canvas.create_line(x1, y1 + 18, x2, y2 - 18, fill=color, width=3)

        for nodes in levels.values():
            for node in nodes:
                x, y = positions[node.node_id]
                selected = node.node_id in selected_path
                fill = self.colors["teal"] if selected else self.colors["surface_alt"]
                text_color = "#FFFFFF" if selected else self.colors["ink"]
                if self.high_contrast and selected:
                    fill = self.colors["yellow"]
                    text_color = "#101010"

                canvas.create_rectangle(
                    x - 72,
                    y - 20,
                    x + 72,
                    y + 20,
                    fill=fill,
                    outline=self.colors["line"],
                    width=1,
                    tags=(f"node:{node.node_id}",),
                )
                label = node.label if len(node.label) <= 18 else node.label[:16] + ".."
                canvas.create_text(
                    x,
                    y,
                    text=label,
                    fill=text_color,
                    width=128,
                    font=("Segoe UI", 8, "bold"),
                    tags=(f"node:{node.node_id}",),
                )
                canvas.tag_bind(
                    f"node:{node.node_id}",
                    "<Button-1>",
                    lambda _event, node_id=node.node_id: self._choose_node(node_id)
                    if node_id != self.current_tree.root.node_id
                    else None,
                )

    def _append_history(self, text: str) -> None:
        self.history.insert(0, text)
        self.history = self.history[:8]
        if self.history_box is None:
            return
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("1.0", "\n\n".join(self.history))
        self.history_box.configure(state="disabled")

    def _open_help(self) -> None:
        messagebox.showinfo(
            "Ayuda - POST-TRUTH",
            "Objetivo: mantener a Ciudad Nova informada y con baja desinformacion.\n\n"
            "1. Lee la publicacion de Civitas.\n"
            "2. Escoge una respuesta.\n"
            "3. Revisa el impacto esperado.\n"
            "4. Confirma la decision.\n\n"
            "El arbol n-ario permite que cada publicacion tenga varias rutas de "
            "consecuencias. DFS y BFS estan disponibles en Modo sustentacion.",
        )

    def _toggle_contrast(self) -> None:
        self.high_contrast = not self.high_contrast
        self.colors = CONTRAST_COLORS if self.high_contrast else BASE_COLORS
        self._configure_style()
        self._build_layout()
        self._load_tree(self.current_tree, restart_timer=False, log_event=False)
        self._render_city()
        self.status_text.set(
            "Modo de alto contraste activado." if self.high_contrast else "Modo visual normal."
        )

    def _button(self, parent: tk.Widget, text: str, command, style: str = "primary") -> tk.Button:
        if style == "quiet":
            bg = self.colors["surface_alt"]
            fg = self.colors["ink"]
            active = self.colors["line"]
        else:
            bg = self.colors["teal"]
            fg = "#FFFFFF"
            active = self.colors["coral"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _panel(self, parent: tk.Widget, padx: int = 14, pady: int = 13) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=self.colors["surface"],
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=self.colors["line"],
        )

    def _decision_nodes(self) -> list[DecisionNode]:
        nodes = [node for node in self.current_tree.dfs_nodes() if node is not self.current_tree.root]
        leaves = [node for node in nodes if not node.children]
        return leaves if leaves else nodes

    def _event_badge_text(self, tree: DecisionTree) -> str:
        if tree.event.truth_level >= 75:
            trust = "alta"
        elif tree.event.truth_level >= 40:
            trust = "media"
        else:
            trust = "baja"
        return f"{tree.event.kind} | veracidad {trust}"

    def _impact_summary(self, impact: Impact) -> str:
        parts = [
            f"Verificacion {impact.verified_information:+}",
            f"Confianza {impact.trust:+}",
            f"Convivencia {impact.coexistence:+}",
            f"Bienestar {impact.digital_wellbeing:+}",
            f"Desinfo {impact.misinformation:+}",
            f"Conflictos {impact.conflicts:+}",
            f"Puntos {impact.score:+}",
        ]
        return " | ".join(parts)

    def _selected_path_label(self) -> str:
        if not self.selected_node_id:
            return ""
        return " > ".join(node.label for node in self.current_tree.path_to(self.selected_node_id))

    def _feedback_for(self, impact: Impact) -> str:
        if impact.verified_information > 8 and impact.misinformation < 0:
            return "Buena jugada: la ciudad recibio contexto y bajo la desinformacion."
        if impact.misinformation > 8 or impact.conflicts > 5:
            return "Decision riesgosa: el rumor gano fuerza y subio la tension."
        if impact.coexistence > 3:
            return "La conversacion mejoro y la comunidad se calmo."
        return "La ciudad reacciono a tu decision."

    def _city_health(self) -> int:
        positive = (
            self.city.verified_information
            + self.city.trust
            + self.city.coexistence
            + self.city.digital_wellbeing
        )
        protective = (100 - self.city.misinformation) + (100 - self.city.conflicts)
        return round((positive + protective) / 6)
