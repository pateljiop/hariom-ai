import threading
import tkinter as tk
from tkinter import messagebox, filedialog

from .activity import ActivityBus
from .agent import PersonalAgent
from .ai_router import AIRouter
from .browser import BrowserController
from .computer import ComputerController
from .github_tools import GitHubTools
from .tools import ToolRegistry
from .workspace import Workspace


class App(tk.Tk):
    BG = "#10131a"
    PANEL = "#171b24"
    TEXT = "#f2f5f9"
    MUTED = "#8d97a8"
    ACCENT = "#74d7ff"
    ENTRY = "#0c0f15"

    def __init__(self):
        super().__init__()
        self.title("Hariom AI")
        self.geometry("430x610+40+80")
        self.minsize(360, 500)
        self.configure(bg=self.BG)
        self.overrideredirect(True)
        self.attributes("-alpha", 0.94)
        self.attributes("-topmost", True)

        self._drag_x = 0
        self._drag_y = 0
        self.activity = ActivityBus()
        self.router = AIRouter(self.activity)
        self.ws = Workspace()
        self.browser = BrowserController(self.activity, headless=False)
        self.computer = ComputerController(self.activity)
        self.github = GitHubTools(self.activity)
        self.tools = ToolRegistry(
            self.ws, self.activity, browser=self.browser,
            computer=self.computer, github=self.github
        )
        self.agent = PersonalAgent(self.router, self.ws, self.activity, tools=self.tools)
        self.current_task = None
        self.build()
        self.activity.subscribe(self.log_line)
        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit("SYSTEM -> Hariom AI personal agent ready")

        self.bind("<Control-space>", lambda _e: self.toggle_visibility())
        self.bind("<Escape>", lambda _e: self.withdraw())

    def build(self):
        outer = tk.Frame(self, bg=self.BG, highlightthickness=1, highlightbackground="#303846")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=self.PANEL, height=48)
        header.pack(fill="x")
        header.bind("<ButtonPress-1>", self.start_drag)
        header.bind("<B1-Motion>", self.drag)
        tk.Label(
            header, text="◉  HARIOM AI", bg=self.PANEL, fg=self.TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(side="left", padx=14)
        tk.Label(
            header, text="PERSONAL AI", bg=self.PANEL, fg=self.MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(side="left")
        tk.Button(
            header, text="×", command=self.destroy, bg=self.PANEL, fg=self.MUTED,
            activebackground=self.PANEL, activeforeground=self.TEXT,
            relief="flat", bd=0, font=("Segoe UI", 16), padx=10
        ).pack(side="right")

        orb = tk.Frame(outer, bg=self.BG, height=130)
        orb.pack(fill="x")
        self.orb = tk.Label(
            orb, text="◉", bg=self.BG, fg=self.ACCENT,
            font=("Segoe UI", 58, "bold")
        )
        self.orb.pack(pady=(18, 0))
        self.status = tk.StringVar(value="Ready")
        tk.Label(
            orb, textvariable=self.status, bg=self.BG, fg=self.MUTED,
            font=("Segoe UI", 9)
        ).pack()

        command = tk.Frame(outer, bg=self.PANEL, padx=12, pady=10)
        command.pack(fill="x", padx=12, pady=(0, 10))
        self.prompt = tk.Text(
            command, height=3, wrap="word", bg=self.ENTRY, fg=self.TEXT,
            insertbackground=self.ACCENT, relief="flat", bd=0,
            font=("Segoe UI", 10), padx=10, pady=8
        )
        self.prompt.pack(fill="x")
        self.prompt.insert("1.0", "Ask Hariom AI...")
        self.prompt.bind("<FocusIn>", self.clear_placeholder)
        self.prompt.bind("<Control-Return>", lambda _e: self.run_task())

        actions = tk.Frame(command, bg=self.PANEL)
        actions.pack(fill="x", pady=(8, 0))
        self.action_button(actions, "Ask", self.ask).pack(side="left")
        self.action_button(actions, "Run Task", self.run_task).pack(side="left", padx=6)
        self.action_button(actions, "Approve", self.approve_task).pack(side="left")
        self.action_button(actions, "Resume", self.resume_saved).pack(side="right")

        tk.Label(
            outer, text="LIVE ACTIVITY", bg=self.BG, fg=self.MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=16)

        activity_box = tk.Frame(outer, bg=self.ENTRY)
        activity_box.pack(fill="both", expand=True, padx=12, pady=(5, 8))
        self.log = tk.Text(
            activity_box, wrap="word", state="disabled", bg=self.ENTRY,
            fg="#b8c2d1", insertbackground=self.TEXT, relief="flat", bd=0,
            font=("Consolas", 8), padx=9, pady=8
        )
        self.log.pack(fill="both", expand=True)

        footer = tk.Frame(outer, bg=self.PANEL)
        footer.pack(fill="x")
        self.footer_status = tk.Label(
            footer, text="Ctrl+Space: show/hide  •  Esc: hide",
            bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)
        )
        self.footer_status.pack(side="left", padx=12, pady=8)
        tk.Button(
            footer, text="Workspace", command=self.list_workspace,
            bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL,
            activeforeground=self.TEXT, relief="flat", bd=0,
            font=("Segoe UI", 8)
        ).pack(side="right", padx=8)

    def action_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command,
            bg="#222936", fg=self.TEXT, activebackground="#303a4b",
            activeforeground=self.TEXT, relief="flat", bd=0,
            padx=12, pady=5, font=("Segoe UI", 8, "bold"), cursor="hand2"
        )

    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def drag(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry("+%d+%d" % (x, y))

    def toggle_visibility(self):
        if self.state() == "withdrawn":
            self.deiconify()
            self.lift()
        else:
            self.withdraw()

    def clear_placeholder(self, _event=None):
        if self.prompt.get("1.0", "end").strip() == "Ask Hariom AI...":
            self.prompt.delete("1.0", "end")

    def get_prompt(self):
        value = self.prompt.get("1.0", "end").strip()
        return "" if value == "Ask Hariom AI..." else value

    def log_line(self, line):
        self.after(0, lambda: self.append(self.log, line))
        self.after(0, lambda: self.status.set(line[:75]))
        self.after(0, self.pulse_orb)

    def pulse_orb(self):
        self.orb.configure(fg="#c8f1ff")
        self.after(180, lambda: self.orb.configure(fg=self.ACCENT))

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def ask(self):
        prompt = self.get_prompt()
        if not prompt:
            return
        threading.Thread(target=self.ask_worker, args=(prompt,), daemon=True).start()

    def ask_worker(self, prompt):
        try:
            text, provider = self.router.chat(
                prompt,
                system="You are Hariom AI, a personal AI assistant. Be practical and transparent. Never claim an action was performed unless a tool verified it.",
            )
            self.after(0, lambda: self.append(self.log, "AI (" + provider + "): " + text))
            self.after(0, lambda: self.status.set("Ready"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("AI error", str(exc)))

    def run_task(self):
        prompt = self.get_prompt()
        if not prompt:
            return
        threading.Thread(target=self.task_worker, args=(prompt,), daemon=True).start()

    def task_worker(self, prompt):
        try:
            self.after(0, lambda: self.status.set("Planning task..."))
            state = self.agent.run(prompt, approve=False)
            self.current_task = state
            self.after(0, lambda: self.show_task(state))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Task error", str(exc)))

    def resume_saved(self):
        saved = self.agent.checkpoints.list()
        candidates = [
            (tid, state) for tid, state in saved
            if state.status.value not in ("completed", "failed")
        ]
        if not candidates:
            self.append(self.log, "No resumable saved task found.")
            return
        task_id, state = candidates[0]
        self.current_task = state
        self.append(self.log, "RESUME: " + task_id + " -> " + state.status.value)
        threading.Thread(target=self.resume_worker, args=(task_id,), daemon=True).start()

    def resume_worker(self, task_id):
        try:
            state = self.agent.resume(task_id, approve=False)
            self.current_task = state
            self.after(0, lambda: self.show_task(state))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Resume error", str(exc)))

    def approve_task(self):
        if not self.current_task:
            self.append(self.log, "No task is waiting for approval.")
            return
        threading.Thread(target=self.approve_worker, daemon=True).start()

    def approve_worker(self):
        try:
            state = self.agent.execute(self.current_task, approve=True)
            self.current_task = state
            self.after(0, lambda: self.show_task(state))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Task error", str(exc)))

    def show_task(self, state):
        self.status.set("Task: " + state.status.value)
        for i, step in enumerate(state.steps, 1):
            self.append(self.log, "%s. [%s] %s" % (i, step["status"], step["description"]))
            if step.get("output"):
                self.append(self.log, "   " + step["output"][:1000])
        if state.result:
            self.append(self.log, state.result)

    def list_workspace(self):
        try:
            items = self.ws.list_files()
            self.append(
                self.log,
                "\n".join(str(p.relative_to(self.ws.root)) for p in items[:100])
                or "Workspace is empty."
            )
        except Exception as exc:
            messagebox.showerror("Workspace", str(exc))

    def choose_workspace(self):
        path = filedialog.askdirectory(initialdir=str(self.ws.root))
        if path:
            self.ws = Workspace(path)
            self.agent.workspace = self.ws
            self.agent.tools.workspace = self.ws
            self.activity.emit("SYSTEM -> workspace changed to " + str(self.ws.root))


def launch():
    App().mainloop()
