import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .activity import ActivityBus
from .agent import PersonalAgent
from .ai_router import AIRouter
from .browser import BrowserController
from .tools import ToolRegistry
from .workspace import Workspace


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hariom AI - Personal AI")
        self.geometry("1200x760")
        self.minsize(900, 600)
        self.activity = ActivityBus()
        self.router = AIRouter(self.activity)
        self.ws = Workspace()
        self.browser = BrowserController(self.activity, headless=False)
        self.tools = ToolRegistry(self.ws, self.activity, browser=self.browser)
        self.agent = PersonalAgent(self.router, self.ws, self.activity, tools=self.tools)
        self.current_task = None
        self.build()
        self.activity.subscribe(self.log_line)
        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit("SYSTEM -> Hariom AI personal agent ready")

    def build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="HARIOM AI", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(top, text="Personal AI OS", font=("Segoe UI", 11)).pack(side="left", padx=12)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(panes, padding=8)
        right = ttk.Frame(panes, padding=8)
        panes.add(left, weight=3)
        panes.add(right, weight=2)

        ttk.Label(left, text="Chat / Task").pack(anchor="w")
        self.prompt = tk.Text(left, height=7, wrap="word")
        self.prompt.pack(fill="x", pady=6)
        self.prompt.insert("1.0", "Tell Hariom AI what you want...")

        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Ask AI", command=self.ask).pack(side="left")
        ttk.Button(buttons, text="Run Task", command=self.run_task).pack(side="left", padx=6)
        ttk.Button(buttons, text="Approve & Continue", command=self.approve_task).pack(side="left")
        ttk.Button(buttons, text="Workspace", command=self.list_workspace).pack(side="left", padx=6)
        ttk.Button(buttons, text="Choose", command=self.choose_workspace).pack(side="left")

        ttk.Label(left, text="Response / Task Result").pack(anchor="w", pady=(12, 4))
        self.response = tk.Text(left, wrap="word", state="disabled")
        self.response.pack(fill="both", expand=True)

        ttk.Label(right, text="Live Activity").pack(anchor="w")
        self.log = tk.Text(right, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, pady=6)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def log_line(self, line):
        self.after(0, lambda: self.append(self.log, line))
        self.after(0, lambda: self.status.set(line))

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def refresh(self):
        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit("SYSTEM -> providers available: " + (", ".join(self.router.available()) or "none"))
        self.activity.emit("SYSTEM -> browser tools registered")

    def ask(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            return
        self.append(self.response, "You: " + prompt)
        threading.Thread(target=self.ask_worker, args=(prompt,), daemon=True).start()

    def ask_worker(self, prompt):
        try:
            text, provider = self.router.chat(
                prompt,
                system="You are Hariom AI, a personal AI assistant. Be practical and transparent. Never claim an action was performed unless a tool verified it.",
            )
            self.after(0, lambda: self.append(self.response, "Hariom AI (" + provider + "):\n" + text))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("AI error", str(exc)))

    def run_task(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            return
        self.append(self.response, "TASK: " + prompt)
        threading.Thread(target=self.task_worker, args=(prompt,), daemon=True).start()

    def task_worker(self, prompt):
        try:
            state = self.agent.run(prompt, approve=False)
            self.current_task = state
            self.after(0, lambda: self.show_task(state))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Task error", str(exc)))

    def approve_task(self):
        if not self.current_task:
            self.append(self.response, "No task is waiting for approval.")
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
        lines = ["Task status: " + state.status.value]
        for i, step in enumerate(state.steps, 1):
            lines.append("%s. [%s] %s" % (i, step["status"], step["description"]))
            if step.get("output"):
                lines.append("   " + step["output"][:3000])
        if state.result:
            lines.append("\n" + state.result)
        self.append(self.response, "\n".join(lines))

    def list_workspace(self):
        try:
            items = self.ws.list_files()
            self.append(self.response, "\n".join(str(p.relative_to(self.ws.root)) for p in items[:300]) or "Workspace is empty.")
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
