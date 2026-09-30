"""Bounded visual computer-control loop.

The screenshot is treated as untrusted visual data. The model may propose
desktop actions but cannot grant itself approval.
"""
import os
from typing import Callable


class ComputerLoopError(Exception):
    """Raised for invalid or unsafe computer-loop requests."""


class ComputerControlLoop:
    ALLOWED_TOOLS = frozenset({"computer.click", "computer.type", "computer.key"})
    SCREENSHOT_TOOL = "computer.screenshot"

    def __init__(self, registry, max_iterations=6, approval_checker=None):
        if not 1 <= max_iterations <= 10 or isinstance(max_iterations, bool):
            raise ComputerLoopError("max_iterations must be an integer between 1 and 10.")
        if approval_checker is not None and not callable(approval_checker):
            raise ComputerLoopError("approval_checker must be callable.")
        self.registry = registry
        self.max_iterations = max_iterations
        self.approval_checker = approval_checker

    def _approved(self, tool, arguments):
        if self.approval_checker is None:
            return False
        return bool(self.approval_checker({"tool": tool, "arguments": dict(arguments)}))

    def _observe(self):
        approved = self._approved(self.SCREENSHOT_TOOL, {"persist": False})
        result = self.registry.execute(
            self.SCREENSHOT_TOOL,
            {"approved": approved, "persist": False},
            approved=approved,
        )
        if not result.get("ok"):
            return None, {
                "ok": False,
                "status": "approval_required" if "approval" in result.get("error", "").lower() else "observation_failed",
                "error": result.get("error", "Computer screenshot failed."),
            }
        path = result.get("result")
        return path, None

    def _validate(self, decision):
        if not isinstance(decision, dict):
            raise ComputerLoopError("Computer decision must be an object.")
        if decision.get("done") is True:
            return None
        action = decision.get("action")
        if not isinstance(action, dict):
            raise ComputerLoopError("Computer decision requires an action or done=true.")
        tool = action.get("tool")
        arguments = action.get("arguments", {})
        if tool not in self.ALLOWED_TOOLS:
            raise ComputerLoopError(f"Computer loop does not allow tool '{tool}'.")
        if not isinstance(arguments, dict):
            raise ComputerLoopError("Computer action arguments must be an object.")
        requested = action.get("approved", False)
        if not isinstance(requested, bool):
            raise ComputerLoopError("Computer action approved must be boolean.")
        approved = requested and self._approved(tool, arguments)
        return {"tool": tool, "arguments": arguments, "approved": approved}

    def run(self, decide: Callable, initial_image=None):
        if not callable(decide):
            raise ComputerLoopError("decide must be callable.")

        image_path = initial_image
        history = []
        for iteration in range(1, self.max_iterations + 1):
            if not image_path:
                image_path, failure = self._observe()
                if failure:
                    return {"ok": False, "iterations": iteration - 1, "history": history, **failure}

            decision = decide(image_path, list(history))
            action = self._validate(decision)
            if action is None:
                return {
                    "ok": True, "status": "completed",
                    "iterations": iteration - 1, "history": history,
                }

            result = self.registry.execute(
                action["tool"], action["arguments"], approved=action["approved"]
            )
            event = {"iteration": iteration, "action": action, "result": result}
            history.append(event)
            if not result.get("ok"):
                self._cleanup(image_path)
                return {
                    "ok": False, "status": "action_failed", "iterations": iteration,
                    "error": result.get("error", "Computer action failed."), "history": history,
                }

            self._cleanup(image_path)
            image_path, failure = self._observe()
            if failure:
                return {"ok": False, "iterations": iteration, "history": history, **failure}

        self._cleanup(image_path)
        return {
            "ok": False, "status": "iteration_limit",
            "iterations": self.max_iterations,
            "error": "Computer loop reached its bounded iteration limit.",
            "history": history,
        }

    @staticmethod
    def _cleanup(path):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
