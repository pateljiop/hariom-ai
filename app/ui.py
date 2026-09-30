import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

from .activity import ActivityBus
from .agent import PersonalAgent
from .ai_router import AIRouter
from .browser import BrowserController
from .computer import ComputerController
from .github_tools import GitHubTools
from .tools import ToolRegistry
from .voice import VoiceController
from .public_apis import PublicAPIs
from .workspace import Workspace


class App(tk.Tk):
    BG = "#0b0f16"
    PANEL = "#151b25"
    TEXT = "#f2f5f9"
    MUTED = "#8d97a8"
    ACCENT = "#74d7ff"
    ENTRY = "#090d13"

    def __init__(self):
        super().__init__()
        self.title("Hariom AI")
        self.geometry("116x140+40+120")
        self.configure(bg=self.BG)
        self.overrideredirect(True)
        self.attributes("-alpha", 0.96)
        self.attributes("-topmost", True)
        self._drag_x = self._drag_y = 0
        self._expanded = False
        self.current_task = None
        self.panel_width = 440
        self.panel_height = 650
        self.min_panel_width = 360
        self.max_panel_width = 760
        self.min_panel_height = 500
        self.max_panel_height = 900
        self._robot_photo = None
        self._logo_photo = None

        self.activity = ActivityBus()
        self.router = AIRouter(self.activity)
        self.ws = Workspace()
        self.browser = BrowserController(self.activity, headless=False)
        self.computer = ComputerController(self.activity, locator=self.router.locate_on_screen, state_verifier=self.router.verify_click_state)
        self.github = GitHubTools(self.activity)
        self.voice = VoiceController(self.activity)
        self.public_apis = PublicAPIs(self.activity)
        self.tools = ToolRegistry(
            self.ws, self.activity, browser=self.browser,
            computer=self.computer, github=self.github, voice=self.voice,
            public_apis=self.public_apis
        )
        self.agent = PersonalAgent(self.router, self.ws, self.activity, tools=self.tools)

        self.build_robot()
        self.activity.subscribe(self.log_line)
        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit("SYSTEM -> Hariom AI personal agent ready")

        self.bind("<Control-space>", lambda _e: self.toggle_visibility())
        self.bind("<Escape>", lambda _e: self.collapse())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(250, self._animate_robot)

    def _asset_path(self, filename):
        return Path(__file__).resolve().parent.parent / "public" / "assets" / "images" / filename

    def _load_logo(self, size):
        try:
            from PIL import Image, ImageTk
            path = self._asset_path("09_Transparent_Mascot.png")
            if not path.is_file():
                return None
            image = Image.open(path).convert("RGBA")
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def resize_panel(self, dw=0, dh=0):
        self.panel_width = max(self.min_panel_width, min(self.max_panel_width, self.panel_width + int(dw)))
        self.panel_height = max(self.min_panel_height, min(self.max_panel_height, self.panel_height + int(dh)))
        if self._expanded:
            self.geometry("%dx%d+%d+%d" % (self.panel_width, self.panel_height, self.winfo_x(), self.winfo_y()))
            self.lift()

    def reset_panel_size(self):
        self.panel_width, self.panel_height = 440, 650
        self.resize_panel(0, 0)
    def build_robot(self):
        self.robot_frame = tk.Frame(self, bg=self.BG)
        self.robot_frame.pack(fill="both", expand=True)
        self.robot = tk.Canvas(self.robot_frame, width=116, height=108, bg=self.BG, highlightthickness=0, bd=0)
        self.robot.pack()
        self.draw_robot()
        self.robot.bind("<Button-1>", self.open_panel)
        self.robot.bind("<ButtonPress-3>", self.start_drag)
        self.robot.bind("<B3-Motion>", self.drag)
        self.robot.bind("<Double-Button-1>", lambda _e: self.collapse())
        tk.Label(self.robot_frame, text="HARIOM AI", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 7, "bold")).pack()

    def draw_robot(self, glow=False):
        self.robot.delete("all")
        photo = self._load_logo(94)
        if photo is not None:
            self._robot_photo = photo
            self.robot.create_image(58, 54, image=photo)
            return
        glow_color = "#bdefff" if glow else self.ACCENT
        self.robot.create_oval(12, 8, 104, 100, outline="#253746", width=2)
        self.robot.create_oval(22, 18, 94, 90, fill="#172431", outline=glow_color, width=2)
        self.robot.create_rectangle(35, 31, 81, 68, fill="#202d3a", outline=glow_color, width=2)
        self.robot.create_oval(43, 42, 51, 50, fill=glow_color, outline="")
        self.robot.create_oval(65, 42, 73, 50, fill=glow_color, outline="")
        self.robot.create_line(58, 18, 58, 8, fill=glow_color, width=2)
        self.robot.create_oval(54, 4, 62, 12, fill=glow_color, outline="")
        self.robot.create_arc(45, 51, 71, 64, start=200, extent=140, style="arc", outline=glow_color, width=2)
        self.robot.create_line(31, 73, 22, 82, fill=glow_color, width=3)
        self.robot.create_line(85, 73, 94, 82, fill=glow_color, width=3)
        self.robot.create_oval(50, 74, 66, 84, fill="#111a24", outline=glow_color, width=1)

    def _animate_robot(self):
        try:
            if not self.winfo_exists():
                return
            if not self._expanded and hasattr(self, "robot") and self.robot.winfo_exists():
                self.draw_robot(glow=True)
                self.after(500, self._safe_robot_glow_off)
            self.after(900, self._animate_robot)
        except tk.TclError:
            return

    def _safe_robot_glow_off(self):
        try:
            if not self._expanded and hasattr(self, "robot") and self.robot.winfo_exists():
                self.draw_robot(glow=False)
        except tk.TclError:
            pass

    def open_panel(self, _event=None):
        if self._expanded:
            return
        x, y = self.winfo_x(), self.winfo_y()
        self._expanded = True
        self.geometry("%dx%d+%d+%d" % (self.panel_width, self.panel_height, x, max(20, y - 30)))
        self.build_panel()
        self.lift()

    def collapse(self):
        if not self._expanded:
            return
        x, y = self.winfo_x(), self.winfo_y()
        self._expanded = False
        for child in list(self.winfo_children()):
            child.destroy()
        self.geometry("116x140+%d+%d" % (x + 160, y + 30))
        self.build_robot()
        self.lift()

    def build_panel(self):
        for child in list(self.winfo_children()):
            child.destroy()
        outer = tk.Frame(self, bg=self.BG, highlightthickness=1, highlightbackground="#34414f")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=self.PANEL, height=48)
        header.pack(fill="x")
        header.bind("<ButtonPress-1>", self.start_drag)
        header.bind("<B1-Motion>", self.drag)
        tk.Label(header, text="🤖  HARIOM AI", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI", 12, "bold")).pack(side="left", padx=14)
        tk.Label(header, text="PERSONAL AI", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(header, text="—", command=self.collapse, bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", bd=0, font=("Segoe UI", 13), padx=8).pack(side="right")
        tk.Button(header, text="+", command=lambda: self.resize_panel(60, 80), bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", bd=0, font=("Segoe UI", 11, "bold"), padx=7).pack(side="right")
        tk.Button(header, text="-", command=lambda: self.resize_panel(-60, -80), bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", bd=0, font=("Segoe UI", 11, "bold"), padx=7).pack(side="right")
        tk.Button(header, text="R", command=self.reset_panel_size, bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=7).pack(side="right")
        tk.Button(header, text="✕", command=self.quit_app, bg=self.PANEL, fg="#ff8f8f", activebackground=self.PANEL, activeforeground="#ffb0b0", relief="flat", bd=0, font=("Segoe UI", 11, "bold"), padx=8).pack(side="right")

        orb = tk.Frame(outer, bg=self.BG, height=118)
        orb.pack(fill="x")
        self._logo_photo = self._load_logo(88)
        if self._logo_photo is not None:
            self.orb = tk.Label(orb, image=self._logo_photo, bg=self.BG)
        else:
            self.orb = tk.Label(orb, text="◉", bg=self.BG, fg=self.ACCENT, font=("Segoe UI", 54, "bold"))
        self.orb.pack(pady=(6, 0))
        self.status = tk.StringVar(value="Ready")
        tk.Label(orb, textvariable=self.status, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack()

        command = tk.Frame(outer, bg=self.PANEL, padx=12, pady=10)
        command.pack(fill="x", padx=12, pady=(0, 10))
        self.prompt = tk.Text(command, height=3, wrap="word", bg=self.ENTRY, fg=self.TEXT, insertbackground=self.ACCENT, relief="flat", bd=0, font=("Segoe UI", 10), padx=10, pady=8)
        self.prompt.pack(fill="x")
        self.prompt.insert("1.0", "Ask Hariom AI...")
        self.prompt.bind("<FocusIn>", self.clear_placeholder)
        self.prompt.bind("<Control-Return>", lambda _e: self.run_task())

        actions = tk.Frame(command, bg=self.PANEL)
        actions.pack(fill="x", pady=(8, 0))
        self.action_button(actions, "Ask", self.ask).pack(side="left")
        self.action_button(actions, "Run", self.run_task).pack(side="left", padx=4)
        self.action_button(actions, "🎙 Voice", self.voice_command).pack(side="left")
        self.action_button(actions, "👁 Screen", self.see_screen).pack(side="left", padx=4)
        self.action_button(actions, "Approve", self.approve_task).pack(side="left")
        self.action_button(actions, "Resume", self.resume_saved).pack(side="right")

        tk.Label(outer, text="LIVE ACTIVITY", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        box = tk.Frame(outer, bg=self.ENTRY)
        box.pack(fill="both", expand=True, padx=12, pady=(5, 8))
        self.log = tk.Text(box, wrap="word", state="disabled", bg=self.ENTRY, fg="#b8c2d1", relief="flat", bd=0, font=("Consolas", 8), padx=9, pady=8)
        self.log.pack(fill="both", expand=True)

        footer = tk.Frame(outer, bg=self.PANEL)
        footer.pack(fill="x")
        tk.Label(footer, text="Click robot to return  •  Ctrl+Space", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="left", padx=12, pady=8)
        tk.Button(footer, text="Workspace", command=self.list_workspace, bg=self.PANEL, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", bd=0, font=("Segoe UI", 8)).pack(side="right", padx=8)

    def action_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg="#222936", fg=self.TEXT, activebackground="#303a4b", activeforeground=self.TEXT, relief="flat", bd=0, padx=8, pady=5, font=("Segoe UI", 8, "bold"), cursor="hand2")

    def start_drag(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def drag(self, event):
        self.geometry("+%d+%d" % (self.winfo_x() + event.x - self._drag_x, self.winfo_y() + event.y - self._drag_y))

    def quit_app(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        self.destroy()

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
        self.after(0, lambda: self._append_if_open(line))
        self.after(0, lambda: self._set_status(line))
        self.after(0, self.pulse_orb)

    def _append_if_open(self, line):
        if hasattr(self, "log") and self._expanded:
            self.append(self.log, line)

    def _set_status(self, line):
        if hasattr(self, "status") and self._expanded:
            self.status.set(line[:75])

    def pulse_orb(self):
        if hasattr(self, "orb") and self._expanded:
            self.orb.configure(fg="#c8f1ff")
            self.after(180, lambda: self.orb.configure(fg=self.ACCENT))

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def voice_command(self):
        self.status.set("Listening...")
        threading.Thread(target=self.voice_worker, daemon=True).start()

    def voice_worker(self):
        try:
            prompt = self.voice.listen()
            if not prompt:
                self.after(0, lambda: self.status.set("No speech recognized"))
                return
            self.after(0, lambda: self.prompt.delete("1.0", "end"))
            self.after(0, lambda: self.prompt.insert("1.0", prompt))
            self.after(0, lambda: self.status.set("Voice command ready — press Run"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Voice error", str(exc)))

    def see_screen(self):
        self.status.set("Looking at your screen...")
        threading.Thread(target=self.screen_vision_worker, daemon=True).start()

    def screen_vision_worker(self):
        try:
            image = self.computer.screenshot_bytes()
            prompt = self.get_prompt() or (
                "Analyze this computer screenshot. Describe what is currently visible, "
                "identify the main application and important UI elements, and mention "
                "anything that looks like an error or requires attention. Be concise."
            )
            text, provider = self.router.vision_chat(prompt, image)
            self.after(0, lambda: self.append(self.log, "VISION (" + provider + "):\n" + text))
            self.after(0, lambda: self.status.set("Screen analyzed"))
        except Exception as exc:
            error = str(exc)
            self.after(0, lambda error=error: messagebox.showerror("Screen Vision", error))

    def ask(self):
        prompt = self.get_prompt()
        if prompt:
            threading.Thread(target=self.ask_worker, args=(prompt,), daemon=True).start()

    def ask_worker(self, prompt):
        try:
            text, provider = self.router.chat(prompt, system="You are Hariom AI, a personal AI assistant. Be practical and transparent. Never claim an action was performed unless a tool verified it.")
            self.after(0, lambda: self.append(self.log, "AI (" + provider + "): " + text))
            self.after(0, lambda: self.status.set("Ready"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("AI error", str(exc)))

    def run_task(self):
        prompt = self.get_prompt()
        if prompt:
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
        candidates = [(tid, state) for tid, state in saved if state.status.value not in ("completed", "failed")]
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
        if self._expanded:
            self.geometry("%dx%d+%d+%d" % (self.panel_width, self.panel_height, self.winfo_x(), self.winfo_y()))
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
            self.append(self.log, "\n".join(str(p.relative_to(self.ws.root)) for p in items[:100]) or "Workspace is empty.")
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
