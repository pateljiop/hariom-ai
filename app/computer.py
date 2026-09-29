import ctypes
import io
import platform
from pathlib import Path


class ComputerController:
    """Controlled Windows desktop input/output through PyAutoGUI."""

    ALLOWED_BUTTONS = {"left", "middle", "right"}
    ALLOWED_KEYS = {
        "enter", "esc", "tab", "space", "backspace", "delete",
        "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
        "shift", "ctrl", "alt", "win", "capslock",
    }

    def __init__(self, activity):
        self.activity = activity
        self.system = platform.system()
        self._pg = None

    def _pyautogui(self):
        if self.system != "Windows":
            raise RuntimeError("Computer control is supported only on Windows.")
        if self._pg is None:
            try:
                import pyautogui
            except Exception as exc:
                raise RuntimeError(
                    "PyAutoGUI could not be imported: %s: %s" % (type(exc).__name__, exc)
                ) from exc
            pyautogui.FAILSAFE = True
            self._pg = pyautogui
        return self._pg

    def screen_size(self):
        try:
            size = self._pyautogui().size()
            return {"width": size.width, "height": size.height}
        except RuntimeError:
            if self.system == "Windows":
                return {
                    "width": ctypes.windll.user32.GetSystemMetrics(0),
                    "height": ctypes.windll.user32.GetSystemMetrics(1),
                }
            raise

    def position(self):
        point = self._pyautogui().position()
        return {"x": point.x, "y": point.y}

    def screenshot(self, path=None):
        pg = self._pyautogui()
        target = Path(path).expanduser() if path else None
        if target:
            target.parent.mkdir(parents=True, exist_ok=True)
        image = pg.screenshot(str(target) if target else None)
        self.activity.emit("COMPUTER -> screenshot")
        return str(target) if target else image

    def screenshot_bytes(self, image_format="PNG"):
        if self.system != "Windows":
            raise RuntimeError("Screen capture is supported only on Windows.")
        try:
            from PIL import ImageGrab
            image = ImageGrab.grab()
        except Exception as exc:
            raise RuntimeError(
                "Windows screen capture failed: %s: %s" % (type(exc).__name__, exc)
            ) from exc
        buffer = io.BytesIO()
        image.save(buffer, format=str(image_format).upper())
        self.activity.emit("COMPUTER -> screenshot for vision")
        return buffer.getvalue()

    def _check_point(self, x, y):
        size = self.screen_size()
        if not (0 <= int(x) < size["width"] and 0 <= int(y) < size["height"]):
            raise ValueError("Mouse coordinates are outside the screen bounds.")

    def move_mouse(self, x, y, duration=0.2):
        self._check_point(x, y)
        if duration < 0 or duration > 10:
            raise ValueError("duration must be between 0 and 10 seconds.")
        self._pyautogui().moveTo(int(x), int(y), duration=float(duration))
        self.activity.emit(f"COMPUTER -> move mouse ({int(x)}, {int(y)})")
        return {"x": int(x), "y": int(y)}

    def click(self, x, y, button="left", clicks=1):
        self._check_point(x, y)
        if button not in self.ALLOWED_BUTTONS:
            raise ValueError("Unsupported mouse button.")
        if int(clicks) < 1 or int(clicks) > 3:
            raise ValueError("clicks must be between 1 and 3.")
        self._pyautogui().click(int(x), int(y), clicks=int(clicks), button=button)
        self.activity.emit(f"COMPUTER -> click ({int(x)}, {int(y)})")
        return {"clicked": True, "x": int(x), "y": int(y), "button": button}

    def type_text(self, text):
        value = str(text)
        if len(value) > 5000:
            raise ValueError("text is too long.")
        self._pyautogui().write(value, interval=0.01)
        self.activity.emit("COMPUTER -> typed text")
        return {"typed": len(value)}

    def press_key(self, key):
        key = str(key).lower()
        if key not in self.ALLOWED_KEYS and len(key) != 1:
            raise ValueError("Unsupported key.")
        self._pyautogui().press(key)
        self.activity.emit(f"COMPUTER -> key {key}")
        return {"key": key}

    def hotkey(self, *keys):
        normalized = [str(k).lower() for k in keys]
        if not normalized or len(normalized) > 4:
            raise ValueError("hotkey requires 1 to 4 keys.")
        if any(k not in self.ALLOWED_KEYS and len(k) != 1 for k in normalized):
            raise ValueError("Unsupported hotkey key.")
        self._pyautogui().hotkey(*normalized)
        self.activity.emit("COMPUTER -> hotkey")
        return {"keys": normalized}

    def wait(self, seconds=1):
        seconds = float(seconds)
        if seconds < 0 or seconds > 30:
            raise ValueError("seconds must be between 0 and 30.")
        self._pyautogui().sleep(seconds)
        return {"waited": seconds}
