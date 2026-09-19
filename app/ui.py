import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .config import WORKSPACE, PROVIDERS
from .activity import ActivityBus
from .ai_router import AIRouter
from .workspace import Workspace
from .terminal import run_command
from .agent import Agent


BG = "#070B14"
PANEL = "#0D1422"
PANEL_2 = "#111B2D"
PANEL_3 = "#15233A"
BORDER = "#20324D"
TEXT = "#F4F7FB"
MUTED = "#8392A8"
BLUE = "#00D9FF"
BLUE_2 = "#007BFF"
RED = "#FF2D55"
GREEN = "#35D07F"
PURPLE = "#8B7CFF"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hariom AI")
        self.geometry("1500x900")
        self.minsize(1180, 720)
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
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure(
            "Primary.TButton",
            background=BLUE_2,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 10),
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
        style.map("Secondary.TButton", background=[("active", PANEL_3)])
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
        body.pack(fill="both", expand=True, padx=16, pady=(8, 12))

        self._build_nav(body)

        center = tk.Frame(body, bg=BG)
        center.pack(side="left", fill="both", expand=True, padx=(10, 10))

        right = tk.Frame(
            body, bg=PANEL, width=330,
            highlightthickness=1, highlightbackground=BORDER
        )
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._build_center(center)
        self._build_right(right)

        self.status = tk.StringVar(value="Ready")
        tk.Label(
            self,
            textvariable=self.status,
            bg="#050810",
            fg=MUTED,
            anchor="w",
            padx=16,
            pady=7,
            font=("Segoe UI", 9),
        ).pack(fill="x", side="bottom")

    def _build_header(self):
        header = tk.Frame(self, bg=BG, height=74)
        header.pack(fill="x", padx=16, pady=(12, 0))
        header.pack_propagate(False)

        mark = tk.Canvas(header, width=48, height=48, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 10), pady=6)
        mark.create_oval(3, 3, 45, 45, fill=PANEL_2, outline=BLUE, width=2)
        mark.create_arc(7, 7, 41, 41, start=205, extent=130, outline=RED, width=3)
        mark.create_text(24, 25, text="H", fill=TEXT, font=("Segoe UI", 21, "bold"))

        title = tk.Frame(header, bg=BG)
        title.pack(side="left")
        tk.Label(
            title, text="HARIOM", bg=BG, fg=TEXT,
            font=("Segoe UI", 20, "bold")
        ).pack(side="left")
        tk.Label(
            title, text=" AI", bg=BG, fg=BLUE,
            font=("Segoe UI", 20, "bold")
        ).pack(side="left")
        tk.Label(
            title, text="BUILD  •  AUTOMATE  •  CREATE  •  TOGETHER",
            bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")

        search = tk.Frame(
            header, bg=PANEL, highlightthickness=1, highlightbackground=BORDER
        )
        search.pack(side="left", fill="x", expand=True, padx=55, ipady=2)
        tk.Label(search, text="⌕", bg=PANEL, fg=MUTED, font=("Segoe UI", 18)).pack(side="left", padx=10)
        tk.Label(
            search,
            text="Ask anything...  (e.g. Build a website, fix errors, add feature, automate...)",
            bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 9)
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            search, text="Ctrl + K", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(side="right", padx=10)

        online = tk.Frame(header, bg=BG)
        online.pack(side="right", padx=(0, 4))
        tk.Label(
            online, text="H", bg=PANEL_2, fg=BLUE,
            font=("Segoe UI", 12, "bold"), width=3, pady=5
        ).pack(side="left")
        tk.Label(
            online, text="Hariom AI\nYour AI Partner",
            bg=BG, fg=TEXT, justify="left",
            font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=8)
        tk.Label(online, text="●", bg=BG, fg=GREEN, font=("Segoe UI", 13)).pack(side="left")

    def _build_nav(self, body):
        nav = tk.Frame(
            body, bg=PANEL, width=220,
            highlightthickness=1, highlightbackground=BORDER
        )
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        tk.Label(
            nav, text="COMMAND CENTER", bg=PANEL, fg=BLUE,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=16, pady=(18, 12))

        for label in ("⌁  Command Center", "▣  Workspace", "▤  Projects", "□  Files",
                      ">_  Terminal", "◆  Git", "◎  Browser", "⌘  Automation", "⚙  Settings"):
            active = label.startswith("⌁")
            b = tk.Button(
                nav, text=label, anchor="w",
                bg=PANEL_3 if active else PANEL,
                fg=TEXT if active else MUTED,
                activebackground=PANEL_3,
                activeforeground=TEXT,
                relief="flat", bd=0, padx=14, pady=10,
                font=("Segoe UI", 9, "bold" if active else "normal"),
                cursor="hand2",
            )
            b.pack(fill="x", padx=8, pady=2)

        tk.Frame(nav, bg=BORDER, height=1).pack(fill="x", padx=12, pady=12)

        tk.Label(nav, text="AI PROVIDER", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 6))

        self.provider = tk.StringVar(value="Auto")
        self.provider_box = ttk.Combobox(
            nav, textvariable=self.provider, state="readonly",
            values=["Auto", "Gemini", "Mistral", "OpenAI", "Groq", "OpenRouter", "Cerebras"],
        )
        self.provider_box.pack(fill="x", padx=12)
        self.provider_box.bind("<<ComboboxSelected>>", self._provider_changed)

        self.model_label = tk.Label(
            nav, text="Auto routing", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8), anchor="w"
        )
        self.model_label.pack(fill="x", padx=14, pady=(6, 0))

        tk.Label(
            nav, text="●  CONNECTED", bg="#0C241A", fg=GREEN,
            font=("Segoe UI", 8, "bold"), padx=8, pady=6
        ).pack(fill="x", padx=12, pady=(10, 12))

        tk.Frame(nav, bg=BORDER, height=1).pack(fill="x", padx=12, pady=2)

        tk.Label(nav, text="SYSTEM STATUS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(14, 7))

        for label, value in (
            ("Agent Engine", "Online"),
            ("File System", "Ready"),
            ("Git Integration", "Ready"),
            ("Approval System", "Active"),
        ):
            row = tk.Frame(nav, bg=PANEL)
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text="●", bg=PANEL, fg=GREEN, font=("Segoe UI", 8)).pack(side="left")
            tk.Label(row, text=label, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)
            tk.Label(row, text=value, bg=PANEL, fg=GREEN,
                     font=("Segoe UI", 8)).pack(side="right")

        tk.Label(
            nav,
            text="Your API keys stay local in .env.\nRisky actions require approval.",
            bg=PANEL, fg=MUTED, justify="left",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=14, pady=18)

    def _build_center(self, parent):
        hero = tk.Frame(parent, bg=BG)
        hero.pack(fill="x", pady=(2, 8))
        tk.Label(
            hero, text="Good morning, ", bg=BG, fg=TEXT,
            font=("Segoe UI", 23, "bold")
        ).pack(side="left")
        tk.Label(
            hero, text="Hariom!", bg=BG, fg=BLUE,
            font=("Segoe UI", 23, "bold")
        ).pack(side="left")
        tk.Label(
            hero, text="\nWhat should we build today?",
            bg=BG, fg=MUTED, font=("Segoe UI", 10)
        ).pack(side="left", padx=12, pady=(14, 0))

        card = tk.Frame(
            parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER
        )
        card.pack(fill="x")

        self.prompt = tk.Text(
            card, height=5, wrap="word", bg=PANEL, fg=TEXT,
            insertbackground=BLUE, selectbackground=BLUE_2,
            relief="flat", bd=0, padx=16, pady=14,
            font=("Segoe UI", 11)
        )
        self.prompt.pack(fill="x")
        self.prompt.insert("1.0", "Describe what you want Hariom AI to do...")

        actions = tk.Frame(card, bg=PANEL)
        actions.pack(fill="x", padx=12, pady=(0, 12))

        for label in ("Build a website", "Fix this error", "Add dark mode",
                      "Create an API", "Automate this task", "Explain this code"):
            tk.Button(
                actions, text=label, bg=PANEL_2, fg=MUTED,
                activebackground=PANEL_3, activeforeground=TEXT,
                relief="flat", bd=0, padx=10, pady=6,
                font=("Segoe UI", 8), cursor="hand2",
                command=lambda value=label: self.set_prompt_hint(value),
            ).pack(side="left", padx=3)

        ttk.Button(
            actions, text="▶  Run Agent", style="Primary.TButton",
            command=self.run_agent
        ).pack(side="right")

        ttk.Button(
            actions, text="Ask AI", style="Secondary.TButton",
            command=self.ask
        ).pack(side="right", padx=7)

        execution = tk.Frame(
            parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER
        )
        execution.pack(fill="both", expand=True, pady=(12, 0))

        head = tk.Frame(execution, bg=PANEL)
        head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(
            head, text="🤖  Agent Execution", bg=PANEL, fg=TEXT,
            font=("Segoe UI", 11, "bold")
        ).pack(side="left")
        tk.Label(
            head, text="  understands natural language and acts on your workspace",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 8)
        ).pack(side="left")
        tk.Label(
            head, text="●  READY", bg="#0C241A", fg=GREEN,
            font=("Segoe UI", 8, "bold"), padx=8, pady=5
        ).pack(side="right")

        split = tk.Frame(execution, bg=PANEL)
        split.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        steps = tk.Frame(split, bg=PANEL_2, width=190)
        steps.pack(side="left", fill="y", padx=(0, 8))
        steps.pack_propagate(False)
        tk.Label(steps, text="PROGRESS", bg=PANEL_2, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(12, 8))

        self.step_labels = []
        for text in ("Understanding request", "Planning solution", "Creating files",
                     "Running tests", "Verifying result"):
            row = tk.Frame(steps, bg=PANEL_2)
            row.pack(fill="x", padx=10, pady=5)
            dot = tk.Label(row, text="○", bg=PANEL_2, fg=MUTED, font=("Segoe UI", 11))
            dot.pack(side="left")
            label = tk.Label(row, text=text, bg=PANEL_2, fg=MUTED,
                             font=("Segoe UI", 8), anchor="w")
            label.pack(side="left", padx=6)
            self.step_labels.append((dot, label))

        result_panel = tk.Frame(split, bg=PANEL)
        result_panel.pack(side="left", fill="both", expand=True)

        result_head = tk.Frame(result_panel, bg=PANEL)
        result_head.pack(fill="x")
        self.agent_file_label = tk.Label(
            result_head, text="Execution output", bg=PANEL, fg=TEXT,
            font=("Segoe UI", 9, "bold")
        )
        self.agent_file_label.pack(side="left")
        tk.Button(
            result_head, text="Copy", bg=PANEL_2, fg=MUTED,
            activebackground=PANEL_3, activeforeground=TEXT,
            relief="flat", bd=0, padx=10, pady=4,
            command=self.copy_response
        ).pack(side="right")

        self.response = tk.Text(
            result_panel, wrap="word", state="disabled",
            bg="#080C15", fg=TEXT, insertbackground=BLUE,
            selectbackground=BLUE_2, relief="flat", bd=0,
            padx=12, pady=12, font=("Consolas", 9)
        )
        self.response.pack(fill="both", expand=True, pady=(7, 0))

        command = tk.Frame(parent, bg=BG)
        command.pack(fill="x", pady=(8, 0))
        self.command = tk.Entry(
            command, bg=PANEL, fg=TEXT, insertbackground=BLUE,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BLUE, font=("Consolas", 9)
        )
        self.command.pack(side="left", fill="x", expand=True, ipady=8)
        ttk.Button(command, text="Run Terminal", style="Secondary.TButton",
                   command=self.run).pack(side="right", padx=(8, 0))

    def _build_right(self, parent):
        activity_head = tk.Frame(parent, bg=PANEL)
        activity_head.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(activity_head, text="LIVE ACTIVITY", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(activity_head, text="●", bg=PANEL, fg=GREEN,
                 font=("Segoe UI", 12)).pack(side="right")
        tk.Label(parent, text="Operational events — no hidden reasoning",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=14)

        box = tk.Frame(parent, bg="#080B12", highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=12, pady=10)
        self.log = tk.Text(
            box, wrap="word", state="disabled", bg="#080B12", fg="#A9B7C8",
            insertbackground=BLUE, relief="flat", bd=0, padx=9, pady=9,
            font=("Consolas", 8)
        )
        self.log.pack(fill="both", expand=True)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(parent, text="PROJECT FILES", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(8, 5))
        self.file_list = tk.Listbox(
            parent, bg=PANEL_2, fg=TEXT, selectbackground=BLUE_2,
            relief="flat", bd=0, height=8, font=("Segoe UI", 8)
        )
        self.file_list.pack(fill="x", padx=12)
        self.refresh_files()

        quick = tk.Frame(parent, bg=PANEL)
        quick.pack(fill="x", padx=12, pady=10)
        ttk.Button(quick, text="New Project", style="Secondary.TButton",
                   command=self.choose_workspace).pack(side="left", fill="x", expand=True)
        ttk.Button(quick, text="Open Folder", style="Secondary.TButton",
                   command=self.choose_workspace).pack(side="left", fill="x", expand=True, padx=(6, 0))

        tk.Label(
            parent, text="APPROVAL  •  FILES  •  TERMINAL  •  AI  •  GIT",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", padx=14, pady=(2, 12))

    def _provider_changed(self, _event=None):
        provider = self._selected_provider()
        if provider and provider in PROVIDERS:
            model = PROVIDERS[provider].get("model", "configured")
            self.model_label.config(text=model)
        else:
            self.model_label.config(text="Automatic fallback routing")

    def set_prompt_hint(self, text):
        hints = {
            "Build a website": "Build a responsive website for ",
            "Fix this error": "Fix this error in my project: ",
            "Add dark mode": "Add dark mode to my project and test it.",
            "Create an API": "Create a simple API for ",
            "Automate this task": "Automate this task: ",
            "Explain this code": "Explain this code and suggest improvements: ",
        }
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", hints.get(text, text))
        self.prompt.focus_set()

    def refresh_files(self):
        if not hasattr(self, "file_list"):
            return
        self.file_list.delete(0, "end")
        try:
            items = self.ws.list_files()
            for path in items[:100]:
                self.file_list.insert("end", "  " + str(path.relative_to(self.ws.root)))
            if not items:
                self.file_list.insert("end", "  (workspace empty)")
        except Exception as error:
            self.file_list.insert("end", "  Unable to read workspace")

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
        self.after(0, self.refresh_files)
        self.after(0, self._update_progress_from_event)

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _update_progress_from_event(self):
        # Operational progress only; no hidden reasoning is displayed.
        events = self.log.get("1.0", "end").lower()
        states = [
            "understanding request",
            "planning solution",
            "creating files",
            "running tests",
            "verifying result",
        ]
        mapping = [
            "agent -> starting",
            "planning task",
            "step",
            "terminal ->",
            "task complete",
        ]
        progress = 0
        for index, token in enumerate(mapping):
            if token in events:
                progress = max(progress, index + 1)
        for index, (dot, label) in enumerate(self.step_labels):
            if index < progress:
                dot.config(text="✓", fg=GREEN)
                label.config(fg=TEXT)
            elif index == progress and progress < len(self.step_labels):
                dot.config(text="●", fg=BLUE)
                label.config(fg=TEXT)
            else:
                dot.config(text="○", fg=MUTED)
                label.config(fg=MUTED)

    def refresh(self):
        self.activity.emit(
            "SYSTEM -> providers: "
            + (", ".join(self.router.available()) or "none")
        )
        self.refresh_files()

    def copy_response(self):
        try:
            text = self.response.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status.set("Response copied to clipboard")
        except Exception:
            pass

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
                lambda: self.append(self.response, f"HARIOM AI  [{provider}]\n{text}"),
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
        self._set_agent_running(True)
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
                lambda: self.append(self.response, "HARIOM AI AGENT\n" + summary),
            )
            self.after(0, lambda: self.agent_file_label.config(
                text=self._agent_result_label(results)
            ))
        except Exception as error:
            err = str(error)
            self.after(0, lambda err=err: messagebox.showerror("Agent error", err))
        finally:
            self.after(0, lambda: self._set_agent_running(False))

    def _agent_result_label(self, results):
        for item in reversed(results):
            result = item.get("result")
            if isinstance(result, str) and ("Wrote " in result or "Patched " in result):
                return result
        return "Execution output"

    def _set_agent_running(self, running):
        # Keep the first v1 UI simple: status is visual, execution remains in the worker thread.
        color = BLUE if running else GREEN
        text = "●  AGENT WORKING" if running else "●  READY"
        for widget in self.winfo_children():
            pass

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
            self.refresh_files()
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
