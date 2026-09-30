from pathlib import Path
import platform
import time


class ComputerController:
    """Windows desktop controller with explicit, bounded actions."""

    def __init__(self, activity):
        self.activity = activity
        self.system = platform.system()

    def _pyautogui(self):
        if self.system != "Windows":
            raise RuntimeError("Computer control currently supports Windows only.")
        try:
            import pyautogui
            pyautogui.PAUSE = 0.15
            pyautogui.FAILSAFE = True
            return pyautogui
        except ImportError as exc:
            raise RuntimeError(
                "Computer control needs PyAutoGUI. Install with 'pip install pyautogui'."
            ) from exc

    def screen_size(self):
        pyautogui = self._pyautogui()
        size = pyautogui.size()
        return {"width": size.width, "height": size.height}

    def position(self):
        pyautogui = self._pyautogui()
        point = pyautogui.position()
        return {"x": point.x, "y": point.y}

    def screenshot(self, path="computer-screen.png", approved=False):
        if not approved:
            raise PermissionError("Computer screenshot requires explicit approval.")
        pyautogui = self._pyautogui()
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot(str(target))
        self.activity.emit("COMPUTER -> screenshot " + str(target))
        return str(target)

    def move_mouse(self, x, y, duration=0.2):
        pyautogui = self._pyautogui()
        x, y = int(x), int(y)
        size = pyautogui.size()
        if not (0 <= x < size.width and 0 <= y < size.height):
            raise ValueError("Mouse coordinates are outside the screen.")
        pyautogui.moveTo(x, y, duration=float(duration))
        return {"x": x, "y": y}

    def click(self, x=None, y=None, button="left", clicks=1, approved=False):
        if not approved:
            raise PermissionError("Computer click requires explicit approval.")
        pyautogui = self._pyautogui()
        if x is not None or y is not None:
            if x is None or y is None:
                raise ValueError("Both x and y are required.")
            self.move_mouse(x, y)
        if button not in {"left", "right", "middle"}:
            raise ValueError("Unsupported mouse button.")
        count = max(1, min(int(clicks), 3))
        pyautogui.click(button=button, clicks=count)
        self.activity.emit("COMPUTER -> mouse click")
        return True

    def type_text(self, text, interval=0.01, approved=False):
        if not approved:
            raise PermissionError("Computer typing requires explicit approval.")
        pyautogui = self._pyautogui()
        pyautogui.write(str(text), interval=float(interval))
        self.activity.emit("COMPUTER -> typed text")
        return True

    def press_key(self, key, approved=False):
        if not approved:
            raise PermissionError("Computer keyboard control requires explicit approval.")
        pyautogui = self._pyautogui()
        allowed = {
            "enter", "esc", "tab", "space", "backspace", "delete",
            "up", "down", "left", "right", "home", "end",
            "pageup", "pagedown", "ctrl", "alt", "shift", "win",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
            "f9", "f10", "f11", "f12",
        }
        key = str(key).lower()
        if key not in allowed and not (len(key) == 1 and key.isalnum()):
            raise ValueError("Unsupported key.")
        pyautogui.press(key)
        self.activity.emit("COMPUTER -> key press: " + key)
        return True

    def hotkey(self, keys):
        pyautogui = self._pyautogui()
        if not isinstance(keys, (list, tuple)) or not keys:
            raise ValueError("keys must be a non-empty list.")
        normalized = [str(k).lower() for k in keys]
        for key in normalized:
            if key not in {"ctrl", "alt", "shift", "win"} and not (len(key) == 1 and key.isalnum()):
                raise ValueError("Unsupported hotkey key: " + key)
        pyautogui.hotkey(*normalized)
        self.activity.emit("COMPUTER -> hotkey")
        return True

    def wait(self, seconds=1):
        seconds = max(0.0, min(float(seconds), 10.0))
        time.sleep(seconds)
        return True
