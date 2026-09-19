import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .config import WORKSPACE
from .activity import ActivityBus
from .ai_router import AIRouter
from .workspace import Workspace
from .terminal import run_command
from .agent import Agent


BG = "#0B0F1A"
PANEL = "#111827"
PANEL_2 = "#151E2E"
BORDER = "#243247"
TEXT = "#F4F7FB"
MUTED = "#8D9AAF"
BLUE = "#00D9FF"
BLUE_2 = "#007BFF"
RED = "#FF2D55"
GREEN = "#35D07F"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hariom AI")
        self.geometry("1380x820")
        self.minsize(1050, 680)
        self.configure(bg=BG)

        self.activity = ActivityBus()
        self.router = AIRouter(self.activity)
        self.ws = Workspace()
        self.agent = Agent(
            self.router,
            self.ws,
            self.activity,
            approval_callback=self.request_approval,
        )

        self._configure_styles()
        self.build()
        self.activity.subscribe(self.log_line)

        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit(
            "SYSTEM -> providers: "
            + (", ".join(self.router.available()) or "none")
        )

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Card.TLabel", background=PANEL, foreground=TEXT)
        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=BG,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Section.TLabel",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Primary.TButton",
            background=BLUE_2,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#009FE8")])
        style.configure(
            "Secondary.TButton",
            background=PANEL_2,
            foreground=TEXT,
            bordercolor=BORDER,
            padding=(12, 9),
        )
        style.map("Secondary.TButton", background=[("active", "#1B2940")])
        style.configure(
            "Danger.TButton",
            background="#351522",
            foreground="#FF8EA5",
            borderwidth=0,
            padding=(12, 9),
        )
        style.configure(
            "TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=BLUE,
            bordercolor=BORDER,
        )

    def build(self):
        self._build_header()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(8, 14))

        sidebar = tk.Frame(
            body, bg=PANEL, width=235, highlightthickness=1, highlightbackground=BORDER
        )
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        center = tk.Frame(body, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        activity = tk.Frame(
            body, bg=PANEL, width=355, highlightthickness=1, highlightbackground=BORDER
        )
        activity.pack(side="right", fill="y", padx=(12, 0))
        activity.pack_propagate(False)

        self._build_center(center)
        self._build_activity(activity)

        self.status = tk.StringVar(value="Ready")
        status = tk.Label(
            self,
            textvariable=self.status,
            bg="#080B12",
            fg=MUTED,
            anchor="w",
            padx=18,
            pady=7,
            font=("Segoe UI", 9),
        )
        status.pack(fill="x", side="bottom")

    def _build_header(self):
        header = tk.Frame(self, bg=BG, height=76)
        header.pack(fill="x", padx=18, pady=(16, 0))
        header.pack_propagate(False)

        mark = tk.Canvas(header, width=48, height=48, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 10))
        mark.create_oval(4, 4, 44, 44, fill=PANEL_2, outline=BLUE, width=2)
        mark.create_text(24, 25, text="H", fill=TEXT, font=("Segoe UI", 22, "bold"))
        mark.create_arc(8, 8, 40, 40, start=205, extent=130, outline=RED, width=3)

        titlebox = tk.Frame(header, bg=BG)
        titlebox.pack(side="left")
        tk.Label(
            titlebox, text="HARIOM AI", bg=BG, fg=TEXT,
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w")
        tk.Label(
            titlebox, text="PERSONAL AI WORKSTATION  •  LOCAL  •  PRIVATE",
            bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")

        ttk.Button(header, text="Refresh", style="Secondary.TButton",
                   command=self.refresh).pack(side="right", pady=8)

    def _build_sidebar(self, parent):
        tk.Label(
            parent, text="WORKSPACE", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=16, pady=(18, 6))

        self.workspace_label = tk.Label(
            parent, text=str(self.ws.root), bg=PANEL, fg=TEXT,
            justify="left", wraplength=195, font=("Segoe UI", 9)
        )
        self.workspace_label.pack(anchor="w", padx=16)

        ttk.Button(
            parent, text="Choose Workspace", style="Secondary.TButton",
            command=self.choose_workspace
        ).pack(fill="x", padx=14, pady=(12, 4))

        ttk.Button(
            parent, text="List Workspace", style="Secondary.TButton",
            command=self.list_workspace
        ).pack(fill="x", padx=14, pady=4)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=14, pady=16)

        tk.Label(
            parent, text="AI PROVIDER", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.provider = tk.StringVar(value="Auto")
        self.provider_box = ttk.Combobox(
            parent,
            textvariable=self.provider,
            state="readonly",
            values=["Auto", "Gemini", "Mistral", "OpenAI", "Groq", "OpenRouter", "Cerebras"],
        )
        self.provider_box.pack(fill="x", padx=14)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=14, pady=16)

        tk.Label(
            parent, text="SYSTEM", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=16, pady=(0, 7))

        self.system_pill = tk.Label(
            parent, text="●  READY", bg="#10261C", fg=GREEN,
            font=("Segoe UI", 9, "bold"), padx=10, pady=7
        )
        self.system_pill.pack(fill="x", padx=14)

        tk.Label(
            parent,
            text="Your API keys stay in .env.\nRisky actions require approval.",
            bg=PANEL, fg=MUTED, justify="left",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=16, pady=14)

    def _build_center(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x")

        tk.Label(
            top, text="Command Center", bg=BG, fg=TEXT,
            font=("Segoe UI", 16, "bold")
        ).pack(side="left")
        tk.Label(
            top, text="  Tell Hariom AI what you want done.",
            bg=BG, fg=MUTED, font=("Segoe UI", 9)
        ).pack(side="left", pady=3)

        card = tk.Frame(
            parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER
        )
        card.pack(fill="x", pady=(10, 10))

        self.prompt = tk.Text(
            card, height=7, wrap="word", bg=PANEL, fg=TEXT,
            insertbackground=BLUE, selectbackground=BLUE_2,
            relief="flat", borderwidth=0, padx=14, pady=12,
            font=("Segoe UI", 10)
        )
        self.prompt.pack(fill="x")
        self.prompt.insert("1.0", "Describe what you want Hariom AI to do...")

        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(
            controls, text="Ask AI", style="Secondary.TButton", command=self.ask
        ).pack(side="left")
        ttk.Button(
            controls, text="▶  Run Agent", style="Primary.TButton", command=self.run_agent
        ).pack(side="left", padx=7)

        tk.Label(
            controls, text="Agent can inspect files, patch code, run tests and inspect Git.",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 8)
        ).pack(side="right", padx=6)

        response_head = tk.Frame(parent, bg=BG)
        response_head.pack(fill="x")
        tk.Label(
            response_head, text="Response", bg=BG, fg=TEXT,
            font=("Segoe UI", 11, "bold")
        ).pack(side="left")
        tk.Label(
            response_head, text="AI output & execution summary",
            bg=BG, fg=MUTED, font=("Segoe UI", 8)
        ).pack(side="left", padx=8)

        response_card = tk.Frame(
            parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER
        )
        response_card.pack(fill="both", expand=True, pady=(7, 0))

        self.response = tk.Text(
            response_card, wrap="word", state="disabled",
            bg=PANEL, fg=TEXT, insertbackground=BLUE,
            selectbackground=BLUE_2, relief="flat", borderwidth=0,
            padx=14, pady=12, font=("Consolas", 10)
        )
        self.response.pack(fill="both", expand=True)

        command_row = tk.Frame(parent, bg=BG)
        command_row.pack(fill="x", pady=(8, 0))
        self.command = tk.Entry(
            command_row, bg=PANEL, fg=TEXT, insertbackground=BLUE,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BLUE, font=("Consolas", 9)
        )
        self.command.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 7))
        ttk.Button(command_row, text="Run Terminal", style="Secondary.TButton",
                   command=self.run).pack(side="right")

    def _build_activity(self, parent):
        head = tk.Frame(parent, bg=PANEL)
        head.pack(fill="x", padx=14, pady=(16, 8))
        tk.Label(
            head, text="LIVE ACTIVITY", bg=PANEL, fg=TEXT,
            font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        tk.Label(
            head, text="●", bg=PANEL, fg=GREEN,
            font=("Segoe UI", 12, "bold")
        ).pack(side="right")

        tk.Label(
            parent, text="Operational events — no hidden reasoning",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 8)
        ).pack(anchor="w", padx=14)

        box = tk.Frame(parent, bg="#080B12", highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=12, pady=12)

        self.log = tk.Text(
            box, wrap="word", state="disabled",
            bg="#080B12", fg="#A9B7C8", insertbackground=BLUE,
            relief="flat", borderwidth=0, padx=10, pady=10,
            font=("Consolas", 8)
        )
        self.log.pack(fill="both", expand=True)

        tk.Label(
            parent,
            text="APPROVAL  •  FILES  •  TERMINAL  •  AI  •  GIT",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", padx=14, pady=(0, 14))

    def request_approval(self, action, detail):
        event = threading.Event()
        decision = {"approved": False}

        def ask():
            decision["approved"] = messagebox.askyesno(
                "Hariom AI  •  Approval Required",
                f"{detail}\n\nAllow this action?",
                parent=self,
            )
            event.set()

        self.after(0, ask)
        event.wait()
        self.activity.emit(
            f"APPROVAL -> {'allowed' if decision['approved'] else 'denied'}: {action}"
        )
        return decision["approved"]

    def log_line(self, line):
        self.after(0, lambda: self.append(self.log, line))
        self.after(0, lambda: self.status.set(line))

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def refresh(self):
        self.activity.emit(
            "SYSTEM -> providers: "
            + (", ".join(self.router.available()) or "none")
        )

    def ask(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt or prompt == "Describe what you want Hariom AI to do...":
            return
        self.append(self.response, "YOU  >  " + prompt)
        threading.Thread(target=self.ask_worker, args=(prompt,), daemon=True).start()

    def ask_worker(self, prompt):
        try:
            text, provider = self.router.chat(
                prompt,
                preferred=self._selected_provider(),
                system=(
                    "You are Hariom AI, a transparent local workstation assistant. "
                    "Give actionable plans. Never claim an action was performed unless "
                    "a tool actually performed it."
                ),
            )
            self.after(
                0,
                lambda: self.append(
                    self.response, f"HARIOM AI  [{provider}]\n{text}"
                ),
            )
        except Exception as error:
            err = str(error)
            self.after(0, lambda err=err: messagebox.showerror("AI error", err))

    def _selected_provider(self):
        value = self.provider.get().strip().lower()
        return None if value == "auto" else value

    def run_agent(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt or prompt == "Describe what you want Hariom AI to do...":
            return
        self.append(self.response, "YOU  /  AGENT  >  " + prompt)
        self.activity.emit("AGENT -> starting")
        threading.Thread(
            target=self.agent_worker, args=(prompt,), daemon=True
        ).start()

    def agent_worker(self, prompt):
        try:
            summary, results = self.agent.run(
                prompt, preferred=self._selected_provider()
            )
            self.after(
                0,
                lambda: self.append(
                    self.response, "HARIOM AI AGENT\n" + summary
                ),
            )
        except Exception as error:
            err = str(error)
            self.after(0, lambda err=err: messagebox.showerror("Agent error", err))

    def list_workspace(self):
        try:
            items = self.ws.list_files()
            self.append(
                self.response,
                "\n".join(str(p.relative_to(self.ws.root)) for p in items[:300])
                or "Workspace is empty.",
            )
        except Exception as error:
            messagebox.showerror("Workspace", str(error))

    def choose_workspace(self):
        path = filedialog.askdirectory(initialdir=str(self.ws.root))
        if path:
            self.ws = Workspace(path)
            self.agent.workspace = self.ws
            self.workspace_label.config(text=str(self.ws.root))
            self.activity.emit("SYSTEM -> workspace changed to " + str(self.ws.root))

    def run(self):
        command = self.command.get().strip()
        if not command:
            return
        try:
            code, output = run_command(command, self.activity, cwd=self.ws.root)
            self.append(self.response, "$ " + command + "\n" + output)
        except Exception as error:
            messagebox.showwarning("Command blocked", str(error))


def launch():
    App().mainloop()
