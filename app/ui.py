import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from io import BytesIO
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
        self.project_profile = "Current Workspace"
        self.panel_width = 440
        self.panel_height = 650
        self.min_panel_width = 360
        self.max_panel_width = 760
        self.min_panel_height = 500
        self.max_panel_height = 900
        self._robot_photo = None
        self._logo_photo = None
        self.mode = "agent"
        self._screen_photo = None
        self._screen_refresh_job = None
        self._screen_refreshing = False
        self.live_screen_enabled = True

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
        if self._screen_refresh_job is not None:
            try:
                self.after_cancel(self._screen_refresh_job)
            except Exception:
                pass
            self._screen_refresh_job = None
        for child in list(self.winfo_children()):
            child.destroy()
        self.geometry("116x140+%d+%d" % (x + 160, y + 30))
        self.build_robot()
        self.lift()

    def build_panel(self):
        for child in list(self.winfo_children()):
            child.destroy()

        # Product-grade dark glass layout: clear hierarchy, generous spacing,
        # restrained controls, and an always-visible system state.
        outer = tk.Frame(self, bg="#080c12", highlightthickness=1, highlightbackground="#263241")
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg="#0e141d", height=58)
        header.pack(fill="x")
        header.bind("<ButtonPress-1>", self.start_drag)
        header.bind("<B1-Motion>", self.drag)

        brand = tk.Frame(header, bg="#0e141d")
        brand.pack(side="left", padx=(16, 0), pady=10)
        brand.bind("<ButtonPress-1>", self.start_drag)
        brand.bind("<B1-Motion>", self.drag)
        tk.Label(brand, text="HARIOM", bg="#0e141d", fg="#f4f7fb",
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(brand, text=" AI", bg="#0e141d", fg="#79dcff",
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(brand, text="  •  PERSONAL AGENT", bg="#0e141d", fg="#667386",
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=(6, 0))

        controls = tk.Frame(header, bg="#0e141d")
        controls.pack(side="right", padx=8)
        for label, command in (
            ("−", self.collapse),
            ("□", lambda: self.resize_panel(60, 80)),
            ("×", self.quit_app),
        ):
            fg = "#ff8f9a" if label == "×" else "#8290a3"
            tk.Button(controls, text=label, command=command, bg="#0e141d", fg=fg,
                      activebackground="#18212d", activeforeground="#ffffff",
                      relief="flat", bd=0, font=("Segoe UI", 11), width=3,
                      cursor="hand2").pack(side="left")

        # Status strip
        status_bar = tk.Frame(outer, bg="#0b1119", height=30)
        status_bar.pack(fill="x")
        self._status_dot = tk.Label(status_bar, text="●", bg="#0b1119", fg="#67e8a5",
                                    font=("Segoe UI", 8))
        self._status_dot.pack(side="left", padx=(16, 5))
        self.status = tk.StringVar(value="Ready")
        tk.Label(status_bar, textvariable=self.status, bg="#0b1119", fg="#aab5c4",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(status_bar, text="LOCAL WORKSPACE", bg="#0b1119", fg="#596779",
                 font=("Segoe UI", 7, "bold")).pack(side="right", padx=16)

        # Assistant identity / breathing area
        hero = tk.Frame(outer, bg="#080c12", height=112)
        hero.pack(fill="x")
        self._logo_photo = self._load_logo(72)
        if self._logo_photo is not None:
            self.orb = tk.Label(hero, image=self._logo_photo, bg="#080c12")
        else:
            self.orb = tk.Label(hero, text="◉", bg="#080c12", fg="#79dcff",
                                font=("Segoe UI", 48, "bold"))
        self.orb.pack(pady=(10, 0))
        tk.Label(hero, text="Ready when you are.", bg="#080c12", fg="#667386",
                 font=("Segoe UI", 8)).pack()

        # Mode switch: Chat is conversational; Agent can plan and execute tools.
        mode_row = tk.Frame(outer, bg="#080c12")
        mode_row.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(mode_row, text="MODE", bg="#080c12", fg="#617084",
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=(2, 8))
        self.chat_mode_button = tk.Button(mode_row, text="CHAT", command=lambda: self.set_mode("chat"),
                                           relief="flat", bd=0, padx=14, pady=5,
                                           font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.chat_mode_button.pack(side="left")
        self.agent_mode_button = tk.Button(mode_row, text="AGENT", command=lambda: self.set_mode("agent"),
                                            relief="flat", bd=0, padx=14, pady=5,
                                            font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.agent_mode_button.pack(side="left", padx=5)
        self.mode_hint = tk.Label(mode_row, text="", bg="#080c12", fg="#667386",
                                  font=("Segoe UI", 7))
        self.mode_hint.pack(side="left", padx=8)
        self.update_mode_ui()

        # Command surface
        command_card = tk.Frame(outer, bg="#111822", highlightthickness=1,
                                highlightbackground="#1f2a38")
        command_card.pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(command_card, text="COMMAND", bg="#111822", fg="#617084",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(9, 3))

        self.prompt = tk.Text(command_card, height=3, wrap="word",
                              bg="#0b1018", fg="#eef4fa", insertbackground="#79dcff",
                              selectbackground="#294457", relief="flat", bd=0,
                              font=("Segoe UI", 10), padx=11, pady=9)
        self.prompt.pack(fill="x", padx=8)
        self.prompt.insert("1.0", "Tell Hariom AI what to do…")
        self.prompt.bind("<FocusIn>", self.clear_placeholder)
        self.prompt.bind("<Control-Return>", lambda _e: self.run_task())

        action_row = tk.Frame(command_card, bg="#111822")
        action_row.pack(fill="x", padx=8, pady=8)
        self.action_button(action_row, "Ask", self.ask, primary=True).pack(side="left")
        self.action_button(action_row, "Run", self.run_task).pack(side="left", padx=5)
        self.action_button(action_row, "Voice", self.voice_command).pack(side="left")
        self.action_button(action_row, "Screen", self.see_screen).pack(side="left", padx=5)
        self.action_button(action_row, "Approve", self.approve_task).pack(side="right")

        # Live computer view: local-only screen preview, refreshed without blocking the UI.
        screen_card = tk.Frame(outer, bg="#0d141e", highlightthickness=1, highlightbackground="#1b2937")
        screen_card.pack(fill="x", padx=14, pady=(0, 8))
        screen_head = tk.Frame(screen_card, bg="#0d141e")
        screen_head.pack(fill="x", padx=10, pady=(7, 3))
        tk.Label(screen_head, text="LIVE SCREEN", bg="#0d141e", fg="#e4eaf1", font=("Segoe UI", 8, "bold")).pack(side="left")
        self.screen_state = tk.StringVar(value="Local preview")
        tk.Label(screen_head, textvariable=self.screen_state, bg="#0d141e", fg="#67e8a5", font=("Segoe UI", 7, "bold")).pack(side="left", padx=7)
        tk.Button(screen_head, text="Refresh", command=self.refresh_screen, bg="#0d141e", fg="#7c899b", activebackground="#18212d", activeforeground="#eef4fa", relief="flat", bd=0, font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")
        self.screen_preview = tk.Label(screen_card, text="Screen preview will appear here", bg="#080c12", fg="#596779", font=("Segoe UI", 8), height=8)
        self.screen_preview.pack(fill="x", padx=10, pady=(2, 8))
        self.screen_preview.bind("<Button-1>", lambda _e: self.refresh_screen())
        self._schedule_screen_refresh()

        # Live task state: phase, progress and current step.
        task_state = tk.Frame(outer, bg="#0d141e", highlightthickness=1, highlightbackground="#1b2937")
        task_state.pack(fill="x", padx=14, pady=(0, 8))
        task_top = tk.Frame(task_state, bg="#0d141e")
        task_top.pack(fill="x", padx=10, pady=(7, 2))
        self.task_phase = tk.StringVar(value="Ready")
        self.task_progress = tk.StringVar(value="0%")
        self.task_step = tk.StringVar(value="No active task")
        tk.Label(task_top, textvariable=self.task_phase, bg="#0d141e", fg="#dfe8f2", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(task_top, textvariable=self.task_progress, bg="#0d141e", fg="#79dcff", font=("Segoe UI", 8, "bold")).pack(side="right")
        self.task_bar = tk.Canvas(task_state, height=4, bg="#182331", highlightthickness=0, bd=0)
        self.task_bar.pack(fill="x", padx=10, pady=3)
        self.task_bar.bind("<Configure>", lambda _e: self._render_task_progress())
        tk.Label(task_state, textvariable=self.task_step, bg="#0d141e", fg="#7e8b9d", font=("Segoe UI", 7)).pack(anchor="w", padx=10, pady=(1, 7))

        # Activity / response surface
        activity_head = tk.Frame(outer, bg="#080c12")
        activity_head.pack(fill="x", padx=16)
        tk.Label(activity_head, text="TASK TIMELINE", bg="#080c12", fg="#e4eaf1",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(activity_head, text="LIVE", bg="#080c12", fg="#67e8a5",
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=7)
        tk.Button(activity_head, text="Resume", command=self.resume_saved,
                  bg="#080c12", fg="#69778a", activebackground="#111822",
                  activeforeground="#eef4fa", relief="flat", bd=0,
                  font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")

        box = tk.Frame(outer, bg="#0b1018", highlightthickness=1,
                       highlightbackground="#1a2430")
        box.pack(fill="both", expand=True, padx=14, pady=(5, 8))
        self.log = tk.Text(box, wrap="word", state="disabled",
                           bg="#0b1018", fg="#b8c4d3", relief="flat", bd=0,
                           font=("Cascadia Mono", 8), padx=10, pady=9,
                           insertbackground="#79dcff")
        self.log.pack(fill="both", expand=True)

        footer = tk.Frame(outer, bg="#0e141d", height=34)
        footer.pack(fill="x")
        tk.Label(footer, text="Ctrl+Space  show/hide", bg="#0e141d", fg="#586779",
                 font=("Segoe UI", 7)).pack(side="left", padx=14, pady=8)
        tk.Button(footer, text="Workspace", command=self.list_workspace,
                  bg="#0e141d", fg="#7c899b", activebackground="#18212d",
                  activeforeground="#eef4fa", relief="flat", bd=0,
                  font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right", padx=8)
        tk.Button(footer, text="Change", command=self.choose_workspace,
                  bg="#0e141d", fg="#7c899b", activebackground="#18212d",
                  activeforeground="#eef4fa", relief="flat", bd=0,
                  font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")
        tk.Button(footer, text="Brave", command=lambda: self.select_browser("brave"), bg="#0e141d", fg="#7c899b", activebackground="#18212d", activeforeground="#eef4fa", relief="flat", bd=0, font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right", padx=8)
        tk.Button(footer, text="Chromium", command=lambda: self.select_browser("chromium"), bg="#0e141d", fg="#7c899b", activebackground="#18212d", activeforeground="#eef4fa", relief="flat", bd=0, font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")

    def set_mode(self, mode):
        if mode not in ("chat", "agent"):
            return
        self.mode = mode
        self.update_mode_ui()
        if hasattr(self, "status"):
            self.status.set("Chat mode" if mode == "chat" else "Agent mode")

    def update_mode_ui(self):
        if not hasattr(self, "chat_mode_button"):
            return
        active_bg = "#1b789c"
        idle_bg = "#151d29"
        self.chat_mode_button.configure(
            bg=active_bg if self.mode == "chat" else idle_bg,
            fg="#f4f8fb" if self.mode == "chat" else "#7e8b9d",
            activebackground=active_bg, activeforeground="#ffffff")
        self.agent_mode_button.configure(
            bg=active_bg if self.mode == "agent" else idle_bg,
            fg="#f4f8fb" if self.mode == "agent" else "#7e8b9d",
            activebackground=active_bg, activeforeground="#ffffff")
        self.mode_hint.configure(
            text="Conversation only" if self.mode == "chat" else "Plan • tools • verify")

    def action_button(self, parent, text, command, primary=False):
        bg = "#1b789c" if primary else "#1a2330"
        active = "#238db5" if primary else "#253142"
        return tk.Button(parent, text=text, command=command, bg=bg, fg="#f3f7fb",
                         activebackground=active, activeforeground="#ffffff",
                         relief="flat", bd=0, padx=11, pady=6,
                         font=("Segoe UI", 8, "bold"), cursor="hand2")

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
        if self.prompt.get("1.0", "end").strip() == "Tell Hariom AI what to do…":
            self.prompt.delete("1.0", "end")

    def get_prompt(self):
        value = self.prompt.get("1.0", "end").strip()
        return "" if value == "Tell Hariom AI what to do…" else value

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

    def _schedule_screen_refresh(self):
        if not self._expanded or not self.live_screen_enabled:
            return
        if self._screen_refresh_job is not None:
            try:
                self.after_cancel(self._screen_refresh_job)
            except Exception:
                pass
        self._screen_refresh_job = self.after(1800, self._auto_refresh_screen)

    def _auto_refresh_screen(self):
        self._screen_refresh_job = None
        if not self._expanded or not self.live_screen_enabled:
            return
        self.refresh_screen(auto=True)

    def refresh_screen(self, auto=False):
        if self._screen_refreshing or not self._expanded:
            return
        self._screen_refreshing = True
        self.screen_state.set("Updating…" if not auto else "Live")
        threading.Thread(target=self._screen_preview_worker, daemon=True).start()

    def _screen_preview_worker(self):
        try:
            image_bytes = self.computer.screenshot_bytes()
            self.after(0, lambda data=image_bytes: self._update_screen_preview(data))
        except Exception as exc:
            error = str(exc)
            self.after(0, lambda error=error: self._screen_preview_failed(error))

    def _update_screen_preview(self, image_bytes):
        try:
            from PIL import Image, ImageTk
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            max_width = max(280, min(self.panel_width - 48, 700))
            max_height = 220
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self._screen_photo = ImageTk.PhotoImage(image)
            self.screen_preview.configure(image=self._screen_photo, text="", height=1)
            self.screen_state.set("LIVE • local")
        except Exception as exc:
            self._screen_preview_failed(str(exc))
        finally:
            self._screen_refreshing = False
            self._schedule_screen_refresh()

    def _screen_preview_failed(self, error):
        self._screen_refreshing = False
        if hasattr(self, "screen_preview"):
            self.screen_preview.configure(image="", text="Screen preview unavailable")
        if hasattr(self, "screen_state"):
            self.screen_state.set("Unavailable")
        self._schedule_screen_refresh()
        self.append(self.log, "SCREEN -> " + error)

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
        if not prompt:
            return
        if self.mode == "agent":
            self.run_task()
            return
        threading.Thread(target=self.ask_worker, args=(prompt,), daemon=True).start()

    def ask_worker(self, prompt):
        try:
            text, provider = self.router.chat(prompt, system="You are Hariom AI, a personal AI assistant. Be practical, direct, and personalized. Reply only in English or Hinglish. Match the user language: use English for English input and Hinglish for Hindi/Hinglish input. Do not use Devanagari Hindi unless explicitly requested. Never claim an action was performed unless a tool verified it.")
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
        self.current_task = state
        phase = getattr(state, "phase", state.status.value)
        progress = getattr(state, "progress", 0)
        self.status.set("Task: " + phase)
        if hasattr(self, "task_phase"):
            self.task_phase.set(phase)
            self.task_progress.set(str(progress) + "%")
            current = state.current_step
            if 0 <= current < len(state.steps):
                self.task_step.set("Step %d/%d  •  %s" % (current + 1, len(state.steps), state.steps[current].get("description", "")))
            elif state.status.value == "completed":
                self.task_step.set("All steps verified")
            elif state.status.value == "failed":
                self.task_step.set("Task stopped — inspect timeline")
            else:
                self.task_step.set("Preparing execution")
            self._render_task_progress()
        marker = getattr(self, "_last_rendered_task", None)
        if marker == state.updated_at:
            return
        self._last_rendered_task = state.updated_at
        self.append(self.log, "TASK -> %s (%d%%)" % (phase, progress))
        for i, step in enumerate(state.steps, 1):
            self.append(self.log, "%s. [%s] %s" % (i, step["status"], step["description"]))
            if step.get("output"):
                self.append(self.log, "   " + step["output"][:1000])
        if state.result:
            self.append(self.log, state.result)

    def _render_task_progress(self):
        if not hasattr(self, "task_bar"):
            return
        self.task_bar.delete("all")
        width = max(1, self.task_bar.winfo_width())
        try:
            progress = max(0, min(100, int(self.task_progress.get().rstrip("%"))))
        except ValueError:
            progress = 0
        self.task_bar.create_rectangle(0, 0, width * progress / 100, 4,
                                       fill="#4fc3f7", outline="")

    def list_workspace(self):
        try:
            items = self.ws.list_files()
            self.append(self.log, "\n".join(str(p.relative_to(self.ws.root)) for p in items[:100]) or "Workspace is empty.")
        except Exception as exc:
            messagebox.showerror("Workspace", str(exc))

    def select_browser(self, browser):
        try:
            selected = self.browser.set_browser(browser)
            self.status.set("Browser: " + selected)
            self.append(self.log, "BROWSER -> selected " + selected)
        except Exception as exc:
            messagebox.showerror("Browser", str(exc))

    def choose_workspace(self):
        path = filedialog.askdirectory(initialdir=str(self.ws.root))
        if path:
            self.ws = Workspace(path)
            self.agent.workspace = self.ws
            self.agent.tools.workspace = self.ws
            self.activity.emit("SYSTEM -> workspace changed to " + str(self.ws.root))


def launch():
    App().mainloop()
