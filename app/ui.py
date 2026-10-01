import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .activity import ActivityBus
from .ai_router import AIRouter
from .workspace import Workspace
from .computer import ComputerController
from .workstation import Workstation, WorkstationError


class App(tk.Tk):
    """Windows desktop UI backed by the real agent/task/approval architecture."""

    def __init__(self):
        super().__init__()
        self.title("Hariom AI - Personal Workstation")
        self.geometry("1280x820")
        self.minsize(1000, 650)
        self.activity = ActivityBus()
        self.router = AIRouter(self.activity)
        self.ws = Workspace()
        self.computer = ComputerController(self.activity)
        self.workstation = Workstation(activity=self.activity, workspace=self.ws).attach_router(self.router)
        self.screen_image = None
        self.pending_approval = None
        self.build()
        self.activity.subscribe(self.log_line)
        self.activity.emit("SYSTEM -> workspace: " + str(self.ws.root))
        self.activity.emit("SYSTEM -> providers: " + (", ".join(self.router.available()) or "none"))

    def build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="HARIOM AI", font=("Segoe UI", 20, "bold")).pack(side="left")
        self.state_var = tk.StringVar(value="Ready")
        ttk.Label(top, textvariable=self.state_var).pack(side="left", padx=20)
        ttk.Button(top, text="View Screen", command=self.view_screen).pack(side="right", padx=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(panes, padding=8)
        right = ttk.Frame(panes, padding=8)
        panes.add(left, weight=3)
        panes.add(right, weight=2)

        ttk.Label(left, text="Task / Chat").pack(anchor="w")
        self.prompt = tk.Text(left, height=7, wrap="word")
        self.prompt.pack(fill="x", pady=6)
        self.prompt.insert("1.0", "Describe what you want Hariom AI to do...")
        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Run Agent", command=self.run_agent).pack(side="left")
        ttk.Button(buttons, text="Tool Loop", command=self.run_tool_loop).pack(side="left", padx=6)
        ttk.Button(buttons, text="Background", command=self.run_background).pack(side="left", padx=6)
        ttk.Button(buttons, text="List Workspace", command=self.list_workspace).pack(side="left")
        ttk.Button(buttons, text="Choose Workspace", command=self.choose_workspace).pack(side="left", padx=6)
        ttk.Button(buttons, text="Browser Agent", command=self.run_browser_agent).pack(side="left", padx=6)
        ttk.Button(buttons, text="Computer Agent", command=self.run_computer_agent).pack(side="left")

        approval = ttk.Frame(left)
        approval.pack(fill="x", pady=(8, 0))
        ttk.Label(approval, text="Approval:").pack(side="left")
        self.approval_entry = ttk.Entry(approval)
        self.approval_entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(approval, text="Approve Commit", command=self.approve).pack(side="left")
        ttk.Button(approval, text="Reject", command=self.reject).pack(side="left", padx=4)

        ttk.Label(left, text="Response").pack(anchor="w", pady=(12, 4))
        self.response = tk.Text(left, wrap="word", state="disabled")
        self.response.pack(fill="both", expand=True)

        ttk.Label(right, text="Live Activity / Task State").pack(anchor="w")
        self.log = tk.Text(right, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, pady=6)
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.task_id = tk.Entry(row)
        self.task_id.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Status", command=self.show_status).pack(side="left", padx=5)
        ttk.Button(row, text="Cancel", command=self.cancel_task).pack(side="left")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def log_line(self, line):
        self.after(0, lambda: self.append(self.log, line))
        self.after(0, lambda: self.status.set(line))
        self.after(0, lambda: self.state_var.set(line))

    def append(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", str(text) + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def refresh(self):
        self.activity.emit("SYSTEM -> providers: " + (", ".join(self.router.available()) or "none"))

    def view_screen(self):
        try:
            path = self.computer.screenshot(approved=True, persist=False)
            image = tk.PhotoImage(file=path)
            try:
                os.unlink(path)
            except OSError:
                pass
            width, height = image.width(), image.height()
            max_width, max_height = 1100, 700
            scale = max(1, (width + max_width - 1) // max_width, (height + max_height - 1) // max_height)
            if scale > 1:
                image = image.subsample(scale, scale)
            window = tk.Toplevel(self)
            window.title("Hariom AI - Live Screen Snapshot")
            window.geometry(f"{min(image.width()+20,1120)}x{min(image.height()+60,740)}")
            frame = ttk.Frame(window, padding=8)
            frame.pack(fill="both", expand=True)
            label = ttk.Label(frame, image=image)
            label.pack(expand=True)
            label.image = image
            self.screen_image = image
        except Exception as exc:
            messagebox.showwarning("Screen View", str(exc))

    def _request(self):
        request = self.prompt.get("1.0", "end").strip()
        if not request or request == "Describe what you want Hariom AI to do...":
            return None
        return request

    def run_agent(self):
        request = self._request()
        if not request:
            return
        self.append(self.response, "You: " + request)
        threading.Thread(target=self._run_agent_worker, args=(request,), daemon=True).start()

    def _run_agent_worker(self, request):
        try:
            result = self.workstation.prepare(request)
            self.after(0, lambda: self._show_agent_result(result))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Agent error", str(exc)))

    def _show_agent_result(self, result):
        self.append(self.response, "Agent result:\n" + repr(result))
        state = result.get("state", {}) if isinstance(result, dict) else {}
        task_id = state.get("task_id") if isinstance(state, dict) else None
        if task_id:
            self.task_id.delete(0, "end")
            self.task_id.insert(0, task_id)
        request_id = result.get("request_id") if isinstance(result, dict) else None
        if request_id:
            self.pending_approval = request_id
            self.append(self.log, "APPROVAL REQUIRED -> " + request_id)
            self.approval_entry.focus_set()

    def _visual_approval(self, request):
        event = threading.Event()
        decision = {"approved": False}
        def ask_user():
            label = request.get("tool", "desktop action")
            args = request.get("arguments", {})
            approved = messagebox.askyesno(
                "Hariom AI approval",
                "Allow this action?\\n\\nTool: %s\\nArguments: %s" % (label, args),
                parent=self,
            )
            decision["approved"] = bool(approved)
            event.set()
        self.after(0, ask_user)
        event.wait(timeout=300)
        return decision["approved"]

    def run_tool_loop(self):
        request = self._request()
        if not request:
            return
        threading.Thread(target=self._tool_loop_worker, args=(request,), daemon=True).start()

    def _tool_loop_worker(self, request):
        try:
            result = self.workstation.run_tool_loop(
                request,
                approval_checker=self._visual_approval,
            )
            self.after(0, lambda: self.append(self.response, "Tool loop:\\n" + repr(result)))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Tool loop", str(exc)))

    def run_browser_agent(self):
        request = self._request()
        if not request:
            return
        threading.Thread(target=self._browser_worker, args=(request,), daemon=True).start()

    def _browser_worker(self, request):
        try:
            result = self.workstation.run_browser(
                request,
                approval_checker=self._visual_approval,
            )
            self.after(0, lambda: self.append(self.response, "Browser agent:\\n" + repr(result)))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Browser agent", str(exc)))

    def run_computer_agent(self):
        request = self._request()
        if not request:
            return
        threading.Thread(target=self._computer_worker, args=(request,), daemon=True).start()

    def _computer_worker(self, request):
        try:
            result = self.workstation.run_computer(
                request,
                approval_checker=self._visual_approval,
            )
            self.after(0, lambda: self.append(self.response, "Computer agent:\\n" + repr(result)))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Computer agent", str(exc)))

    def run_background(self):
        request = self._request()
        if not request:
            return
        threading.Thread(target=self._background_worker, args=(request,), daemon=True).start()

    def _background_worker(self, request):
        try:
            result = self.workstation.submit_background(request)
            self.after(0, lambda: self.append(self.response, "Background task queued: " + repr(result)))
            self.after(0, lambda: self.task_id.delete(0, "end"))
            task_id = result.get("task_id")
            if task_id:
                self.after(0, lambda: self.task_id.insert(0, task_id))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Background task", str(exc)))

    def approve(self):
        request_id = self.pending_approval
        message = self.approval_entry.get().strip() or "Approved by user"
        if not request_id:
            messagebox.showinfo("Approval", "No pending approval request.")
            return
        threading.Thread(target=self._approval_worker, args=(request_id, message), daemon=True).start()

    def _approval_worker(self, request_id, message):
        try:
            result = self.workstation.approve(request_id, message)
            self.after(0, lambda: self.append(self.response, "Approved:\n" + repr(result)))
            self.pending_approval = None
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Approval", str(exc)))

    def reject(self):
        request_id = self.pending_approval
        if not request_id:
            messagebox.showinfo("Approval", "No pending approval request.")
            return
        try:
            result = self.workstation.reject(request_id)
            self.append(self.response, "Rejected:\n" + repr(result))
            self.pending_approval = None
        except Exception as exc:
            messagebox.showerror("Approval", str(exc))

    def show_status(self):
        task_id = self.task_id.get().strip()
        if not task_id:
            return
        try:
            result = self.workstation.status(task_id)
            self.append(self.response, "Task status:\n" + repr(result))
        except Exception as exc:
            messagebox.showwarning("Task status", str(exc))

    def cancel_task(self):
        task_id = self.task_id.get().strip()
        if not task_id:
            return
        try:
            result = self.workstation.cancel(task_id)
            self.append(self.response, "Cancelled:\n" + repr(result))
        except Exception as exc:
            messagebox.showwarning("Cancel task", str(exc))

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
            self.computer.activity = self.activity
            self.workstation = Workstation(activity=self.activity, workspace=self.ws).attach_router(self.router)
            self.activity.emit("SYSTEM -> workspace changed to " + str(self.ws.root))

    def destroy(self):
        try:
            self.workstation.shutdown()
        finally:
            super().destroy()


def launch():
    App().mainloop()
