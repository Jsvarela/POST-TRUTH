from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from post_truth.sustentation import SustentationWindow

from post_truth.decision_tree import DecisionNode, DecisionTree, load_trees
from post_truth.game_state import CityState
from post_truth.models import Impact, Role


ROOT_DIR = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT_DIR / "data" / "events.json"

NORMAL = {
    "bg": "#0F172A", "panel": "#172033", "panel2": "#202B40",
    "text": "#F8FAFC", "muted": "#A8B3C7", "accent": "#38BDF8",
    "good": "#34D399", "warn": "#FBBF24", "bad": "#FB7185",
    "line": "#334155",
}

CONTRAST = {
    "bg": "#000000", "panel": "#111111", "panel2": "#1A1A1A",
    "text": "#FFFFFF", "muted": "#FFFFFF", "accent": "#00FFFF",
    "good": "#00FF66", "warn": "#FFFF00", "bad": "#FF4D4D",
    "line": "#FFFFFF",
}

ROLE_INFO = {
    Role.CITIZEN.value: "Equilibrado.",
    Role.JOURNALIST.value: "Favorece la verificación.",
    Role.INFLUENCER.value: "Amplifica el impacto para bien o para mal.",
    Role.CANDIDATE.value: "Sus decisiones pesan más sobre la confianza.",
}

METRICS = [
    ("verified_information", "Información verificada", False),
    ("trust", "Confianza", False),
    ("coexistence", "Convivencia", False),
    ("digital_wellbeing", "Bienestar", False),
    ("misinformation", "Desinformación", True),
    ("conflicts", "Conflictos", True),
]


class DecisionGameApp(tk.Tk):

    def __init__(self) -> None:
        super().__init__()

        self.title("POST-TRUTH - Ciudad Nova")
        self.geometry("1160x740")
        self.minsize(1000, 650)

        self.city = CityState()
        self.trees = load_trees(EVENTS_PATH)

        self.role_name = tk.StringVar(value=Role.CITIZEN.value)
        self.high_contrast = tk.BooleanVar(value=False)

        self.role = Role.CITIZEN

        self.events: list[DecisionTree] = []
        self.event_index = 0

        self.current_tree: DecisionTree | None = None
        self.current_node: DecisionNode | None = None

        self.timer_id: str | None = None
        self.seconds_left = 15

        self.metric_widgets: dict[str, tuple[tk.Label, tk.Canvas]] = {}

        self._show_start()

    @property
    def c(self) -> dict[str, str]:
        if self.high_contrast.get():
            return CONTRAST

        return NORMAL

    def _clear(self) -> None:
        self._cancel_timer()

        for widget in self.winfo_children():
            widget.destroy()

        self.configure(bg=self.c["bg"])

    def _panel(
        self,
        parent: tk.Widget,
        padx: int = 18,
        pady: int = 16
    ) -> tk.Frame:

        return tk.Frame(
            parent,
            bg=self.c["panel"],
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=self.c["line"]
        )

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        primary: bool = True
    ) -> tk.Button:

        return tk.Button(
            parent,
            text=text,
            command=command,
            relief="flat",
            bd=0,
            bg=self.c["accent"] if primary else self.c["panel2"],
            fg="#07111C" if primary else self.c["text"],
            activebackground=self.c["good"] if primary else self.c["line"],
            activeforeground="#07111C" if primary else self.c["text"],
            padx=14,
            pady=10,
            cursor="hand2",
            font=("Segoe UI", 10, "bold")
        )

    # -------------------------------------------------
    # INICIO
    # -------------------------------------------------

    def _show_start(self) -> None:

        self._clear()

        card = self._panel(self, 48, 42)

        card.place(
            relx=.5,
            rely=.5,
            anchor="center",
            relwidth=.7
        )

        tk.Label(
            card,
            text="POST-TRUTH",
            bg=self.c["panel"],
            fg=self.c["accent"],
            font=("Segoe UI", 34, "bold")
        ).pack()

        tk.Label(
            card,
            text="CIUDAD NOVA",
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 16, "bold")
        ).pack(pady=(0, 18))

        tk.Label(
            card,
            text=(
                "Civitas está llena de rumores, noticias y contenido manipulado. "
                "Decide qué hacer antes de que la desinformación controle la ciudad."
            ),
            bg=self.c["panel"],
            fg=self.c["muted"],
            wraplength=650,
            justify="center",
            font=("Segoe UI", 11)
        ).pack(pady=(0, 26))

        tk.Label(
            card,
            text="Elige tu rol",
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 11, "bold")
        ).pack()

        role_box = ttk.Combobox(
            card,
            textvariable=self.role_name,
            values=[role.value for role in Role],
            state="readonly",
            width=30
        )

        role_box.pack(pady=(7, 5))

        role_help = tk.Label(
            card,
            text=ROLE_INFO[self.role_name.get()],
            bg=self.c["panel"],
            fg=self.c["muted"],
            font=("Segoe UI", 9)
        )

        role_help.pack(pady=(0, 18))

        role_box.bind(
            "<<ComboboxSelected>>",
            lambda _event:
            role_help.configure(
                text=ROLE_INFO[self.role_name.get()]
            )
        )

        tk.Checkbutton(
            card,
            text="Modo de alto contraste",
            variable=self.high_contrast,
            command=self._show_start,
            bg=self.c["panel"],
            fg=self.c["text"],
            activebackground=self.c["panel"],
            activeforeground=self.c["text"],
            selectcolor=self.c["panel2"],
            font=("Segoe UI", 10)
        ).pack(pady=(0, 18))

        self._button(
            card,
            "COMENZAR PARTIDA",
            self._start_game
        ).pack()

    def _start_game(self) -> None:

        self.role = Role(self.role_name.get())

        self.city.reset()

        self.events = random.sample(
            self.trees,
            len(self.trees)
        )

        self.event_index = 0

        self._build_game()
        self._next_event()

    # -------------------------------------------------
    # PANTALLA PRINCIPAL
    # -------------------------------------------------

    def _build_game(self) -> None:

        self._clear()

        header = tk.Frame(
            self,
            bg=self.c["bg"],
            padx=22,
            pady=14
        )

        header.pack(fill="x")

        tk.Label(
            header,
            text="POST-TRUTH",
            bg=self.c["bg"],
            fg=self.c["accent"],
            font=("Segoe UI", 22, "bold")
        ).pack(side="left")

        self.round_label = tk.Label(
            header,
            bg=self.c["bg"],
            fg=self.c["muted"],
            font=("Segoe UI", 10, "bold")
        )

        self.round_label.pack(
            side="left",
            padx=18
        )

        self.score_label = tk.Label(
            header,
            bg=self.c["bg"],
            fg=self.c["text"],
            font=("Segoe UI", 11, "bold")
        )

        self.score_label.pack(side="right")

        self._button(
            header,
            "Ayuda",
            self._open_help,
            False
        ).pack(
            side="right",
            padx=10
        )
        self._button(
              header,
               "Sustentación",
              self._open_sustentation,
               False
        ).pack(
                side="right"
        )

        body = tk.Frame(
         self,
          bg=self.c["bg"],
         padx=22,
         pady=0
)

        body.pack(
            fill="both",
            expand=True,
            pady=(0, 22)
)

        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(
            body,
            bg=self.c["bg"]
        )

        left.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 14)
        )

        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        post = self._panel(left)

        post.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 14)
        )

        top = tk.Frame(
            post,
            bg=self.c["panel"]
        )

        top.pack(fill="x")

        tk.Label(
            top,
            text="CIVITAS  •  publicación en tendencia",
            bg=self.c["panel"],
            fg=self.c["accent"],
            font=("Segoe UI", 10, "bold")
        ).pack(side="left")

        self.timer_label = tk.Label(
            top,
            text="",
            bg=self.c["panel"],
            fg=self.c["warn"],
            font=("Segoe UI", 12, "bold")
        )

        self.timer_label.pack(side="right")

        self.timer_bar = tk.Canvas(
            post,
            height=8,
            bg=self.c["panel"],
            highlightthickness=0
        )

        self.timer_bar.pack(
            fill="x",
            pady=(12, 14)
        )

        self.post_title = tk.Label(
            post,
            text="",
            bg=self.c["panel"],
            fg=self.c["text"],
            anchor="w",
            justify="left",
            wraplength=720,
            font=("Segoe UI", 19, "bold")
        )

        self.post_title.pack(fill="x")

        self.post_body = tk.Label(
            post,
            text="",
            bg=self.c["panel"],
            fg=self.c["muted"],
            anchor="w",
            justify="left",
            wraplength=720,
            font=("Segoe UI", 11)
        )

        self.post_body.pack(
            fill="x",
            pady=(8, 0)
        )

        actions = self._panel(left)

        actions.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        actions.grid_columnconfigure(0, weight=1)
        actions.grid_rowconfigure(1, weight=1)

        self.action_title = tk.Label(
            actions,
            text="¿Qué haces?",
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 15, "bold")
        )

        self.action_title.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 10)
        )

        self.choice_frame = tk.Frame(
            actions,
            bg=self.c["panel"]
        )

        self.choice_frame.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        self.choice_frame.grid_columnconfigure(
            0,
            weight=1
        )

        self.choice_frame.grid_columnconfigure(
            1,
            weight=1
        )

        feedback_box = tk.Frame(
            actions,
            bg=self.c["panel2"],
            padx=14,
            pady=12
        )

        feedback_box.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(12, 0)
        )

        feedback_box.grid_columnconfigure(
            0,
            weight=1
        )

        self.feedback = tk.Label(
            feedback_box,
            text="",
            bg=self.c["panel2"],
            fg=self.c["muted"],
            justify="left",
            anchor="w",
            wraplength=680,
            font=("Segoe UI", 10)
        )

        self.feedback.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.next_button = self._button(
            feedback_box,
            "Siguiente publicación",
            self._next_event
        )

        self.next_button.grid(
            row=0,
            column=1,
            padx=(12, 0)
        )

        self.next_button.grid_remove()

        right = tk.Frame(
            body,
            bg=self.c["bg"]
        )

        right.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        city_panel = self._panel(right)

        city_panel.pack(
            fill="x",
            pady=(0, 14)
        )

        tk.Label(
            city_panel,
            text="Ciudad Nova",
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        self.city_canvas = tk.Canvas(
            city_panel,
            height=145,
            bg=self.c["panel"],
            highlightthickness=0
        )

        self.city_canvas.pack(
            fill="x",
            pady=(8, 0)
        )

        metrics = self._panel(right)

        metrics.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            metrics,
            text="Estado de la ciudad",
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

        self.metric_widgets = {}

        for attr, label, _risk in METRICS:

            row = tk.Frame(
                metrics,
                bg=self.c["panel"]
            )

            row.pack(
                fill="x",
                pady=(4, 0)
            )

            tk.Label(
                row,
                text=label,
                bg=self.c["panel"],
                fg=self.c["muted"],
                font=("Segoe UI", 9)
            ).pack(side="left")

            value = tk.Label(
                row,
                text="0",
                bg=self.c["panel"],
                fg=self.c["text"],
                font=("Segoe UI", 9, "bold")
            )

            value.pack(side="right")

            bar = tk.Canvas(
                metrics,
                height=8,
                bg=self.c["panel"],
                highlightthickness=0
            )

            bar.pack(
                fill="x",
                pady=(2, 2)
            )

            self.metric_widgets[attr] = (
                value,
                bar
            )

    # -------------------------------------------------
    # EVENTOS Y DECISIONES
    # -------------------------------------------------

    def _next_event(self) -> None:

        self._cancel_timer()

        if self.event_index >= len(self.events):

            self._show_end()
            return

        self.current_tree = self.events[
            self.event_index
        ]

        self.event_index += 1

        self.current_node = (
            self.current_tree.root
        )

        self.city.apply(
            self.current_tree.root.impact
        )

        self.post_title.configure(
            text=self.current_tree.event.title
        )

        self.post_body.configure(
            text=self.current_tree.event.content
        )

        self.round_label.configure(
            text=(
                f"Publicación "
                f"{self.event_index}/"
                f"{len(self.events)}"
            )
        )

        self.feedback.configure(
            text=(
                "No sabes todavía si es verdadera, "
                "falsa o manipulada. "
                "Decide por el contenido."
            )
        )

        self.next_button.grid_remove()

        self._render_choices()
        self._render_city()
        self._start_timer()

    def _render_choices(self) -> None:

        for widget in (
            self.choice_frame.winfo_children()
        ):
            widget.destroy()

        if self.current_node is None:
            return

        if self.current_node is self.current_tree.root:
            title = "¿Qué haces?"
        else:
            title = "¿Qué haces ahora?"

        self.action_title.configure(
            text=title
        )

        for i, node in enumerate(
            self.current_node.children
        ):

            button = tk.Button(
                self.choice_frame,
                text=(
                    f"{node.label}\n\n"
                    f"{node.description}"
                ),
                command=lambda selected=node:
                self._choose(selected),
                bg=self.c["panel2"],
                fg=self.c["text"],
                activebackground=self.c["line"],
                activeforeground=self.c["text"],
                relief="flat",
                bd=0,
                padx=15,
                pady=15,
                justify="left",
                anchor="w",
                wraplength=320,
                cursor="hand2",
                font=("Segoe UI", 10, "bold")
            )

            button.grid(
                row=i // 2,
                column=i % 2,
                sticky="nsew",
                padx=5,
                pady=5
            )

            self.choice_frame.grid_rowconfigure(
                i // 2,
                weight=1
            )

    def _choose(
        self,
        node: DecisionNode,
        timed_out: bool = False
    ) -> None:

        self._cancel_timer()

        self.current_node = node

        impact = (
            node.impact.scaled_for_role(
                self.role
            )
        )

        self.city.apply(impact)

        self._render_city()

        if timed_out:
            prefix = "Se acabó el tiempo. "
        else:
            prefix = ""

        self.feedback.configure(
            text=(
                f"{prefix}"
                f"{node.label}: "
                f"{node.description}\n\n"
                f"Consecuencia: "
                f"{self._impact_text(impact)}"
            )
        )

        if node.children:

            self._render_choices()
            self._start_timer()

        else:

            self._finish_event()

    def _finish_event(self) -> None:

        self._cancel_timer()

        for widget in (
            self.choice_frame.winfo_children()
        ):
            widget.destroy()

        self.action_title.configure(
            text="Resultado"
        )

        self.feedback.configure(
            text=(
                f"{self.feedback.cget('text')}"
                f"\n\n{self._truth_result()}"
            )
        )

        self.next_button.grid()

    # -------------------------------------------------
    # TEMPORIZADOR
    # -------------------------------------------------

    def _start_timer(self) -> None:

        self._cancel_timer()

        self.seconds_left = 15

        self._tick()

    def _tick(self) -> None:

        self.timer_label.configure(
            text=f"{self.seconds_left} s"
        )

        self._draw_timer()

        if self.seconds_left <= 0:

            self.timer_id = None

            self._timeout()
            return

        self.seconds_left -= 1

        self.timer_id = self.after(
            1000,
            self._tick
        )

    def _draw_timer(self) -> None:

        self.timer_bar.delete("all")

        width = max(
            self.timer_bar.winfo_width(),
            1
        )

        percent = max(
            0,
            self.seconds_left / 15
        )

        if percent > .5:
            color = self.c["good"]

        elif percent > .25:
            color = self.c["warn"]

        else:
            color = self.c["bad"]

        self.timer_bar.create_rectangle(
            0,
            0,
            width,
            8,
            fill=self.c["line"],
            outline=""
        )

        self.timer_bar.create_rectangle(
            0,
            0,
            width * percent,
            8,
            fill=color,
            outline=""
        )

    def _timeout(self) -> None:

        if self.current_node is None:
            return

        ignore = next(
            (
                node
                for node
                in self.current_node.children
                if "ignorar"
                in node.label.lower()
            ),
            None
        )

        if ignore:

            self._choose(
                ignore,
                timed_out=True
            )

            return

        penalty = Impact(
            trust=-2,
            digital_wellbeing=-2,
            misinformation=4,
            conflicts=2,
            score=-3
        )

        self.city.apply(penalty)

        self._render_city()

        self.feedback.configure(
            text=(
                "Se acabó el tiempo. "
                "La publicación siguió circulando "
                "sin respuesta.\n\n"
                f"Consecuencia: "
                f"{self._impact_text(penalty)}"
            )
        )

        self._finish_event()

    def _cancel_timer(self) -> None:

        if self.timer_id is not None:

            self.after_cancel(
                self.timer_id
            )

            self.timer_id = None

    # -------------------------------------------------
    # CIUDAD NOVA
    # -------------------------------------------------

    def _render_city(self) -> None:

        for attr, _label, risk in METRICS:

            value = getattr(
                self.city,
                attr
            )

            label, bar = (
                self.metric_widgets[attr]
            )

            label.configure(
                text=str(value)
            )

            self._draw_metric(
                bar,
                value,
                risk
            )

        self.score_label.configure(
            text=(
                f"{self.role.value}  •  "
                f"{self.city.score} pts"
            )
        )

        self._draw_city()

    def _draw_metric(
        self,
        canvas: tk.Canvas,
        value: int,
        risk: bool
    ) -> None:

        canvas.delete("all")

        width = max(
            canvas.winfo_width(),
            1
        )

        if risk:

            if value < 35:
                color = self.c["good"]

            elif value <= 65:
                color = self.c["warn"]

            else:
                color = self.c["bad"]

        else:

            if value < 35:
                color = self.c["bad"]

            elif value <= 65:
                color = self.c["warn"]

            else:
                color = self.c["good"]

        canvas.create_rectangle(
            0,
            0,
            width,
            8,
            fill=self.c["line"],
            outline=""
        )

        canvas.create_rectangle(
            0,
            0,
            width * value / 100,
            8,
            fill=color,
            outline=""
        )

    def _draw_city(self) -> None:

        self.city_canvas.delete("all")

        health = self._city_health()

        if health >= 70:

            mood = "Ciudad estable"
            color = self.c["good"]

        elif health >= 45:

            mood = "Ciudad en tensión"
            color = self.c["warn"]

        else:

            mood = "Crisis digital"
            color = self.c["bad"]

        width = max(
            self.city_canvas.winfo_width(),
            260
        )

        places = [
            (.20, 72, "Colegio"),
            (.50, 55, "Plaza"),
            (.78, 78, "Alcaldía"),
            (.36, 115, "Barrio"),
            (.68, 118, "Parque")
        ]

        for ratio, y, name in places:

            x = width * ratio

            self.city_canvas.create_rectangle(
                x - 32,
                y - 16,
                x + 32,
                y + 16,
                fill=self.c["panel2"],
                outline=color
            )

            self.city_canvas.create_text(
                x,
                y,
                text=name,
                fill=self.c["text"],
                font=("Segoe UI", 8, "bold")
            )

        self.city_canvas.create_text(
            width / 2,
            14,
            text=(
                f"{mood}  •  "
                f"salud {health}%"
            ),
            fill=color,
            font=("Segoe UI", 10, "bold")
        )

    def _city_health(self) -> int:

        positives = (
            self.city.verified_information
            + self.city.trust
            + self.city.coexistence
            + self.city.digital_wellbeing
        )

        protection = (
            100
            - self.city.misinformation
            + 100
            - self.city.conflicts
        )

        return round(
            (positives + protection) / 6
        )

    # -------------------------------------------------
    # AYUDA
    # -------------------------------------------------
    def _open_sustentation(self) -> None:

         if self.current_tree is None:
             return

         SustentationWindow(
               self,
               self.current_tree
            )
    def _open_help(self) -> None:

        messagebox.showinfo(
            "Ayuda - POST-TRUTH",
            "OBJETIVO\n"
            "Mantén alta la información verificada, "
            "confianza, convivencia y bienestar.\n"
            "Mantén baja la desinformación "
            "y los conflictos.\n\n"

            "CÓMO JUGAR\n"
            "• Lee la publicación.\n"
            "• Decide antes de que termine el tiempo.\n"
            "• Algunas decisiones abren una "
            "segunda decisión.\n"
            "• Las consecuencias aparecen "
            "después de actuar.\n\n"

            "ROLES\n"
            "Ciudadano: equilibrado.\n"
            "Periodista: favorece la verificación.\n"
            "Influencer: amplifica impactos.\n"
            "Candidato: afecta más la confianza."
        )

    # -------------------------------------------------
    # FIN
    # -------------------------------------------------

    def _show_end(self) -> None:

        self._clear()

        health = self._city_health()

        if health >= 75:

            result = (
                "Ciudad Nova terminó estable "
                "y bien informada."
            )

        elif health >= 50:

            result = (
                "La ciudad llegó a la elección "
                "con tensión, pero se mantuvo en pie."
            )

        else:

            result = (
                "La desinformación dominó "
                "buena parte de la conversación."
            )

        card = self._panel(
            self,
            48,
            42
        )

        card.place(
            relx=.5,
            rely=.5,
            anchor="center",
            relwidth=.68
        )

        tk.Label(
            card,
            text="FIN DE LA PARTIDA",
            bg=self.c["panel"],
            fg=self.c["accent"],
            font=("Segoe UI", 26, "bold")
        ).pack()

        tk.Label(
            card,
            text=(
                f"Salud de Ciudad Nova: "
                f"{health}%"
            ),
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 18, "bold")
        ).pack(
            pady=(18, 6)
        )

        tk.Label(
            card,
            text=(
                f"Puntuación: "
                f"{self.city.score}"
            ),
            bg=self.c["panel"],
            fg=self.c["text"],
            font=("Segoe UI", 14, "bold")
        ).pack()

        tk.Label(
            card,
            text=result,
            bg=self.c["panel"],
            fg=self.c["muted"],
            wraplength=620,
            justify="center",
            font=("Segoe UI", 11)
        ).pack(pady=20)

        row = tk.Frame(
            card,
            bg=self.c["panel"]
        )

        row.pack()

        self._button(
            row,
            "Jugar de nuevo",
            self._show_start
        ).pack(
            side="left",
            padx=6
        )

        self._button(
            row,
            "Salir",
            self.destroy,
            False
        ).pack(
            side="left",
            padx=6
        )

    # -------------------------------------------------
    # TEXTOS AUXILIARES
    # -------------------------------------------------

    def _truth_result(self) -> str:

        truth = (
            self.current_tree
            .event
            .truth_level
        )

        if truth >= 75:

            return (
                "Después de actuar se confirma "
                "que la información tenía "
                "veracidad alta."
            )

        if truth >= 40:

            return (
                "Después de actuar se ve que "
                "la información necesitaba "
                "más contexto."
            )

        return (
            "Después de actuar se confirma "
            "que la información tenía "
            "veracidad baja o estaba manipulada."
        )

    @staticmethod
    def _impact_text(
        impact: Impact
    ) -> str:

        values = [
            (
                "verificación",
                impact.verified_information
            ),
            (
                "confianza",
                impact.trust
            ),
            (
                "convivencia",
                impact.coexistence
            ),
            (
                "bienestar",
                impact.digital_wellbeing
            ),
            (
                "desinformación",
                impact.misinformation
            ),
            (
                "conflictos",
                impact.conflicts
            ),
            (
                "puntos",
                impact.score
            )
        ]

        changes = [
            f"{name} {value:+}"
            for name, value in values
            if value
        ]

        if not changes:
            return "sin cambios importantes"

        return " • ".join(changes)