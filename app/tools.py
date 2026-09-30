from dataclasses import dataclass
from .terminal import run_command


@dataclass
class Tool:
    name: str
    description: str
    handler: object
    requires_approval: bool = False


class ToolRegistry:
    """Explicit local tool registry for the personal agent."""

    def __init__(self, workspace, activity, browser=None, computer=None, github=None, voice=None, public_apis=None):
        self.workspace = workspace
        self.activity = activity
        self.browser = browser
        self.computer = computer
        self.github = github
        self.voice = voice
        self.public_apis = public_apis
        self._tools = {}
        self.register(Tool("list_files", "List files inside the active workspace.", self.list_files))
        self.register(Tool("read_file", "Read a UTF-8 file inside the active workspace.", self.read_file))
        self.register(Tool("write_file", "Create or replace a UTF-8 file inside the active workspace.", self.write_file, True))
        self.register(Tool("run_command", "Run a terminal command.", self.run_command, True))

        if browser:
            self.register(Tool("browser_open", "Open a public http/https URL in the controlled browser.", browser.open))
            self.register(Tool("browser_set_browser", "Select the controlled browser: Brave or Playwright Chromium.", browser.set_browser))
            self.register(Tool("browser_status", "Report the selected controlled browser and availability.", browser.browser_status))
            self.register(Tool("browser_current_page", "Get the current browser URL and title.", browser.current_page))
            self.register(Tool("browser_read", "Read visible text from a browser page.", browser.read_text))
            self.register(Tool("browser_click", "Click an element selected by CSS.", browser.click))
            self.register(Tool("browser_type", "Fill text into a form element selected by CSS.", browser.type_text, True))
            self.register(Tool("browser_screenshot", "Capture the current browser page.", browser.screenshot))
            self.register(Tool("browser_close", "Close the controlled browser session.", browser.close))

        if computer:
            self.register(Tool("computer_screen_size", "Get the Windows screen dimensions.", computer.screen_size))
            self.register(Tool("computer_position", "Get the current mouse position.", computer.position))
            self.register(Tool("computer_screenshot", "Capture the Windows desktop.", computer.screenshot))
            self.register(Tool("computer_move_mouse", "Move the mouse to screen coordinates.", computer.move_mouse, True))
            self.register(Tool("computer_click", "Click the Windows desktop at coordinates.", computer.click))
            self.register(Tool("computer_click_target", "Freshly locate a visible screen target with AI vision and click its verified center.", computer.click_target))
            self.register(Tool("computer_type", "Type text into the active application.", computer.type_text, True))
            self.register(Tool("computer_press_key", "Press one bounded keyboard key.", computer.press_key, True))
            self.register(Tool("computer_hotkey", "Press a bounded keyboard shortcut.", computer.hotkey, True))
            self.register(Tool("computer_wait", "Wait briefly for an application state to settle.", computer.wait))

        if github:
            self.register(Tool("github_repo", "Read metadata for a GitHub repository.", github.repo))
            self.register(Tool("github_issue", "Read a GitHub issue.", github.issue))
            self.register(Tool("github_list_issues", "List GitHub issues.", github.list_issues))
            self.register(Tool("github_create_issue", "Create a GitHub issue.", github.create_issue, True))
            self.register(Tool("github_create_comment", "Comment on a GitHub issue or pull request.", github.create_comment, True))

        if public_apis:
            self.register(Tool("public_api", "Call an allowlisted read-only public API that requires no API key.", public_apis.call))

        if voice:
            self.register(Tool("voice_listen", "Listen once for a user-spoken command. User must explicitly start this action.", voice.listen))
            self.register(Tool("voice_speak", "Speak text aloud through the local computer.", voice.speak))

    def register(self, tool):
        self._tools[tool.name] = tool

    def names(self):
        return list(self._tools)

    def describe(self):
        return [{"name": t.name, "description": t.description, "requires_approval": t.requires_approval}
                for t in self._tools.values()]

    def get(self, name):
        return self._tools.get(name)

    @staticmethod
    def _sensitive_action(name, arguments):
        if name not in {"browser_click", "computer_click", "computer_click_target"}:
            return False
        text = str(arguments or {}).lower()
        sensitive = ("delete", "remove", "erase", "logout", "sign out", "purchase",
                     "buy", "pay", "payment", "checkout", "confirm", "send", "submit",
                     "publish", "transfer", "withdraw", "password", "credential",
                     "permission", "revoke", "disable")
        return any(term in text for term in sensitive)

    def requires_approval(self, name, arguments=None):
        tool = self.get(name)
        if not tool:
            raise KeyError("Unknown tool: " + str(name))
        return bool(tool.requires_approval or self._sensitive_action(name, arguments))

    @staticmethod
    def _normalize_arguments(name, arguments):
        """Normalize common model-generated argument aliases before dispatch."""
        args = dict(arguments or {})
        if name in {"read_file", "write_file"} and "path" not in args:
            for alias in ("file", "filename", "filepath"):
                if alias in args:
                    args["path"] = args.pop(alias)
                    break
        return args

    def execute(self, name, arguments=None, approved=False):
        tool = self.get(name)
        if not tool:
            raise KeyError("Unknown tool: " + str(name))
        arguments = self._normalize_arguments(name, arguments)
        if self.requires_approval(name, arguments) and not approved:
            raise PermissionError("Approval required for tool: " + str(name))
        return tool.handler(**arguments)

    def list_files(self, limit=300):
        files = self.workspace.list_files()
        return [str(p.relative_to(self.workspace.root)) for p in files[:int(limit)]]

    def read_file(self, path):
        return self.workspace.read_file(path)

    def write_file(self, path, content):
        result = self.workspace.write_file(path, content)
        self.activity.emit("WORKSPACE -> wrote " + str(result))
        return str(result)

    def run_command(self, command, approved=False):
        code, output = run_command(command, self.activity, approved=approved)
        if code != 0:
            raise RuntimeError("Command exited with code %s: %s" % (code, output[-4000:]))
        return output
