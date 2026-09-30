import threading
import time
import uuid
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
from .chat_history import ChatHistoryStore
from .conversation_context import build_context


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
        self.view = "chat"
        self.history = ChatHistoryStore()
        self.current_conversation_id = None
        self.active_provider = "Auto"
        self.task_started_at = None

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
        self.provider_label = tk.Label(status_bar, text="Auto", bg="#0b1119", fg="#8fa0b4",
                                        font=("Segoe UI", 8, "bold"))
        self.provider_label.pack(side="right", padx=(8, 16))
        tk.Label(status_bar, text="Workspace", bg="#0b1119", fg="#596779",
                 font=("Segoe UI", 7, "bold")).pack(side="right")

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
        tk.Label(hero, text="Hariom AI", bg="#080c12", fg="#eef4fa",
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(hero, text="Ready to work", bg="#080c12", fg="#7e8b9d",
                 font=("Segoe UI", 9)).pack(pady=(2, 2))
        tk.Label(hero, text="Inspect, build, test and work across your desktop.", bg="#080c12", fg="#5f6d80",
                 font=("Segoe UI", 8)).pack()
        chips = tk.Frame(hero, bg="#080c12")
        chips.pack(pady=(7, 0))
        for label in ("Files", "Terminal", "Browser", "Screen", "Voice"):
            tk.Label(chips, text=label, bg="#111a24", fg="#8fa0b4",
                     padx=7, pady=3, font=("Segoe UI", 7)).pack(side="left", padx=2)

        # Main navigation: Chat and persistent searchable History.
        nav = tk.Frame(outer, bg="#080c12")
        nav.pack(fill="x", padx=14, pady=(0, 8))
        self.chat_view_button = tk.Button(nav, text="CHAT", command=lambda: self.set_view("chat"),
                                          relief="flat", bd=0, padx=16, pady=5,
                                          font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.chat_view_button.pack(side="left")
        self.history_view_button = tk.Button(nav, text="HISTORY", command=lambda: self.set_view("history"),
                                             relief="flat", bd=0, padx=16, pady=5,
                                             font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.history_view_button.pack(side="left", padx=5)
        self.action_button(nav, "NEW CHAT", self.new_chat, primary=True).pack(side="right")
        self.update_view_ui()

        self.chat_surface = tk.Frame(outer, bg="#080c12")
        self.chat_surface.pack(fill="both", expand=True)

        # Mode switch: Chat is conversational; Agent can plan and execute tools.
        mode_row = tk.Frame(self.chat_surface, bg="#080c12")
        mode_row.pack(fill="x")
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

        command_card = tk.Frame(self.chat_surface, bg="#111822", highlightthickness=1,
                                highlightbackground="#1f2a38")
        command_card.pack(fill="x", pady=(0, 10))
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
        self.approval_button = self.action_button(action_row, "Approve", self.approve_task).pack(side="right")

        activity_head = tk.Frame(self.chat_surface, bg="#080c12")
        activity_head.pack(fill="x")
        tk.Label(activity_head, text="TASK TIMELINE", bg="#080c12", fg="#e4eaf1",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(activity_head, text="LIVE", bg="#080c12", fg="#67e8a5",
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=7)
        tk.Button(activity_head, text="Resume", command=self.resume_saved,
                  bg="#080c12", fg="#69778a", activebackground="#111822",
                  activeforeground="#eef4fa", relief="flat", bd=0,
                  font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")

        split = tk.Frame(self.chat_surface, bg="#080c12")
        split.pack(fill="both", expand=True, pady=(5, 8))
        activity_panel = tk.Frame(split, bg="#0b1018", highlightthickness=1, highlightbackground="#1a2430")
        activity_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        tk.Label(activity_panel, text="Live activity", bg="#0b1018", fg="#e4eaf1",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(9, 2))
        tk.Label(activity_panel, text="Safe execution progress", bg="#0b1018", fg="#596779",
                 font=("Segoe UI", 7)).pack(anchor="w", padx=10, pady=(0, 6))
        self.log = tk.Text(activity_panel, wrap="word", state="disabled",
                           bg="#0b1018", fg="#b8c4d3", relief="flat", bd=0,
                           font=("Cascadia Mono", 8), padx=10, pady=7,
                           insertbackground="#79dcff")
        self.log.pack(fill="both", expand=True)
        workspace_panel = tk.Frame(split, bg="#0b1018", highlightthickness=1, highlightbackground="#1a2430", width=155)
        workspace_panel.pack(side="right", fill="y")
        workspace_panel.pack_propagate(False)
        tk.Label(workspace_panel, text="Workspace", bg="#0b1018", fg="#e4eaf1",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(9, 2))
        self.workspace_path_label = tk.Label(workspace_panel, text=str(self.ws.root.name), bg="#0b1018", fg="#79dcff",
                                             font=("Segoe UI", 8, "bold"), anchor="w")
        self.workspace_path_label.pack(fill="x", padx=10, pady=(0, 7))
        self.workspace_tree = tk.Label(workspace_panel, text="", bg="#0b1018", fg="#8795a7",
                                       font=("Cascadia Mono", 7), justify="left", anchor="nw")
        self.workspace_tree.pack(fill="both", expand=True, padx=10, pady=4)
        tk.Label(workspace_panel, text="Tools", bg="#0b1018", fg="#596779",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(6, 2))
        tk.Label(workspace_panel, text="Files  •  Terminal\nBrowser • Screen\nVoice", bg="#0b1018", fg="#8795a7",
                 font=("Segoe UI", 7), justify="left", anchor="w").pack(fill="x", padx=10)
        self.refresh_workspace_panel()

        self.history_surface = tk.Frame(outer, bg="#080c12")
        self.history_surface.pack(fill="both", expand=True)
        search_row = tk.Frame(self.history_surface, bg="#080c12")
        search_row.pack(fill="x", pady=(0, 8))
        self.history_search = tk.Entry(search_row, bg="#0b1018", fg="#eef4fa",
                                       insertbackground="#79dcff", relief="flat", bd=0,
                                       font=("Segoe UI", 9))
        self.history_search.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 6))
        self.history_search.insert(0, "Search conversations…")
        self.history_search.bind("<FocusIn>", self.clear_history_placeholder)
        self.history_search.bind("<Return>", lambda _e: self.refresh_history())
        self.action_button(search_row, "Search", self.refresh_history, primary=True).pack(side="right")

        history_box = tk.Frame(self.history_surface, bg="#0b1018", highlightthickness=1,
                               highlightbackground="#1a2430")
        history_box.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(history_box, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.history_list = tk.Listbox(history_box, bg="#0b1018", fg="#c5d0dc",
                                       selectbackground="#1b789c", selectforeground="#ffffff",
                                       relief="flat", bd=0, activestyle="none",
                                       font=("Segoe UI", 9), yscrollcommand=scrollbar.set)
        self.history_list.pack(fill="both", expand=True, padx=6, pady=6)
        scrollbar.config(command=self.history_list.yview)
        self.history_list.bind("<Double-Button-1>", self.open_history_item)
        self.refresh_history()
        self.set_view("chat")

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

    def new_chat(self):
        self.current_conversation_id = None
        if hasattr(self, "log"):
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
        if hasattr(self, "prompt"):
            self.prompt.delete("1.0", "end")
            self.prompt.insert("1.0", "Tell Hariom AI what to do…")
        self.set_view("chat")
        self.status.set("New chat")

    def set_mode(self, mode):
        if mode not in ("chat", "agent"):
            return
        self.mode = mode
        self.update_mode_ui()
        if hasattr(self, "status"):
            self.status.set("Chat mode" if mode == "chat" else "Agent mode")

    def set_view(self, view):
        if view not in ("chat", "history"):
            return
        self.view = view
        if view == "chat":
            self.history_surface.pack_forget()
            self.chat_surface.pack(fill="both", expand=True)
            self.status.set("Ready")
        else:
            self.chat_surface.pack_forget()
            self.history_surface.pack(fill="both", expand=True)
            self.refresh_history()
            self.status.set("Chat history")
        self.update_view_ui()

    def update_view_ui(self):
        if not hasattr(self, "chat_view_button"):
            return
        active = "#1b789c"
        idle = "#151d29"
        self.chat_view_button.configure(
            bg=active if self.view == "chat" else idle,
            fg="#f4f8fb" if self.view == "chat" else "#7e8b9d",
            activebackground=active, activeforeground="#ffffff")
        self.history_view_button.configure(
            bg=active if self.view == "history" else idle,
            fg="#f4f8fb" if self.view == "history" else "#7e8b9d",
            activebackground=active, activeforeground="#ffffff")

    def clear_history_placeholder(self, _event=None):
        if self.history_search.get().strip() == "Search conversations…":
            self.history_search.delete(0, "end")

    def refresh_history(self):
        if not hasattr(self, "history_list"):
            return
        query = self.history_search.get().strip()
        if query == "Search conversations…":
            query = ""
        self._history_results = self.history.search(query, limit=100)
        self._history_conversations = []
        self.history_list.delete(0, "end")
        if not self._history_results:
            self.history_list.insert("end", "No conversations found.")
            return
        seen = set()
        for item in self._history_results:
            cid = item["conversation_id"]
            if cid in seen:
                continue
            seen.add(cid)
            self._history_conversations.append(cid)
            snippet = item["content"].replace("\n", " ").strip()
            if len(snippet) > 72:
                snippet = snippet[:72] + "…"
            role = "You" if item["role"] == "user" else "AI"
            stamp = time.strftime("%d %b %H:%M", time.localtime(item["created"]))
            self.history_list.insert("end", "%s  •  %s  •  %s" % (stamp, role, snippet))

    def open_history_item(self, _event=None):
        if not getattr(self, "_history_results", None):
            return
        selection = self.history_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(getattr(self, "_history_conversations", [])):
            return
        conversation_id = self._history_conversations[index]
        conversation = self.history.conversation(conversation_id)
        self.current_conversation_id = conversation_id
        self.set_view("chat")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        for message in conversation:
            label = "YOU" if message["role"] == "user" else "AI"
            self.append(self.log, "%s: %s" % (label, message["content"]))
        self.status.set("Loaded history")

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

    def see_screen(self):
        self.status.set("Observing screen...")
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
            self.after(0, lambda: self.status.set("Ready"))
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
            if not self.current_conversation_id:
                self.current_conversation_id = uuid.uuid4().hex
            conversation_id = self.current_conversation_id
            previous = self.history.conversation(conversation_id)
            messages = build_context(previous, self.agent.intelligence.system_prompt())
            self.history.add(conversation_id, "user", prompt)
            message, provider = self.router.chat_messages(messages, use_cache=False)
            self.active_provider = provider
            self.after(0, lambda provider=provider: self.provider_label.configure(text=provider))
            text = message.get("content", "")
            self.history.add(conversation_id, "assistant", text)
            self.after(0, lambda: self.append(self.log, "YOU: " + prompt))
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
            self.task_started_at = time.time()
            self.after(0, lambda: self.status.set("Planning..."))
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
        if not self.current_task or self.current_task.status.value != "waiting_approval":
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
        label = state.status.value.replace("_", " ").title()
        self.status.set(label)
        if hasattr(self, "task_started_at") and not self.task_started_at:
            self.task_started_at = time.time()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        for i, step in enumerate(state.steps, 1):
            icon = "✓" if step["status"] == "completed" else ("●" if step["status"] == "running" else ("✕" if step["status"] == "failed" else "○"))
            self.append(self.log, "%s  %s  %s" % (icon, step["status"].title(), step["description"]))
            if step.get("output"):
                self.append(self.log, "    " + step["output"][:500])
        if state.status.value == "waiting_approval":
            self.append(self.log, "⚠ Approval required")
            self.append(self.log, "Hariom wants to perform the protected action shown above.")
        elif state.status.value == "completed":
            elapsed = time.time() - self.task_started_at if self.task_started_at else 0
            completed = sum(1 for step in state.steps if step["status"] == "completed")
            self.append(self.log, "✓ Task completed and verified.")
            self.append(self.log, "Validation: %d/%d steps verified" % (completed, len(state.steps)))
            self.append(self.log, "Time: %.1fs" % elapsed)
            self.refresh_workspace_panel()
        elif state.status.value == "failed":
            self.append(self.log, "✕ Task failed")
            if state.errors:
                self.append(self.log, "What failed: " + state.errors[-1][:700])
            self.append(self.log, "Next: review the failed step above, then retry or adjust the request.")
        if state.result and state.status.value not in ("completed", "failed"):
            self.append(self.log, state.result)

    def refresh_workspace_panel(self):
        if not hasattr(self, "workspace_tree"):
            return
        try:
            items = self.ws.list_files()[:12]
            lines = []
            for path in items:
                try:
                    rel = path.relative_to(self.ws.root)
                except ValueError:
                    rel = path.name
                lines.append("├ " + str(rel))
            self.workspace_tree.configure(text="\n".join(lines) if lines else "Workspace is empty")
        except Exception:
            self.workspace_tree.configure(text="Workspace unavailable")

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
