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

    def __init__(self, workspace, activity, browser=None):
        self.workspace = workspace
        self.activity = activity
        self.browser = browser
        self._tools = {}
        self.register(Tool("list_files", "List files inside the active workspace.", self.list_files))
        self.register(Tool("read_file", "Read a UTF-8 file inside the active workspace.", self.read_file))
        self.register(Tool("write_file", "Create or replace a UTF-8 file inside the active workspace.", self.write_file, True))
        self.register(Tool("run_command", "Run a terminal command.", self.run_command, True))
        if browser:
            self.register(Tool("browser_open", "Open a public http/https URL in the controlled browser.", browser.open))
            self.register(Tool("browser_current_page", "Get the current browser URL and title.", browser.current_page))
            self.register(Tool("browser_read", "Read visible text from a browser page.", browser.read_text))
            self.register(Tool("browser_click", "Click an element selected by CSS.", browser.click, True))
            self.register(Tool("browser_type", "Fill text into a form element selected by CSS.", browser.type_text, True))
            self.register(Tool("browser_screenshot", "Capture the current browser page.", browser.screenshot))
            self.register(Tool("browser_close", "Close the controlled browser session.", browser.close))

    def register(self, tool):
        self._tools[tool.name] = tool

    def names(self):
        return list(self._tools)

    def describe(self):
        return [{"name": t.name, "description": t.description, "requires_approval": t.requires_approval}
                for t in self._tools.values()]

    def get(self, name):
        return self._tools.get(name)

    def execute(self, name, arguments=None, approved=False):
        tool = self.get(name)
        if not tool:
            raise KeyError("Unknown tool: " + str(name))
        if tool.requires_approval and not approved:
            raise PermissionError("Approval required for tool: " + str(name))
        return tool.handler(**(arguments or {}))

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
