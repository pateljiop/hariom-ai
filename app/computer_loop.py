"""Bounded visual computer-control loop.

The screenshot is treated as untrusted visual data. The model may propose
desktop actions but cannot grant itself approval.
"""
import hashlib
import json
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

    def _screen_geometry(self):
        result = self.registry.execute("computer.screen_size", {}, approved=False)
        if not result.get("ok"):
            raise ComputerLoopError(result.get("error", "Unable to read screen dimensions."))
        geometry = result.get("result")
        if not isinstance(geometry, dict):
            raise ComputerLoopError("Screen dimensions must be an object.")
        try:
            width, height = int(geometry["width"]), int(geometry["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ComputerLoopError("Invalid screen dimensions.") from exc
        if not 1 <= width <= 32768 or not 1 <= height <= 32768:
            raise ComputerLoopError("Screen dimensions are outside safe bounds.")
        return {"width": width, "height": height}

    @staticmethod
    def _validate_coordinates(tool, arguments, geometry):
        if tool != "computer.click":
            return
        x, y = arguments.get("x"), arguments.get("y")
        if x is None or y is None:
            return
        if isinstance(x, bool) or isinstance(y, bool):
            raise ComputerLoopError("Click coordinates must be integers.")
        if not isinstance(x, int) or not isinstance(y, int):
            raise ComputerLoopError("Click coordinates must be integers.")
        if not (0 <= x < geometry["width"] and 0 <= y < geometry["height"]):
            raise ComputerLoopError("Click coordinates are outside the current screen.")

    def _approved(self, tool, arguments):
        if self.approval_checker is None:
            return False
        return bool(self.approval_checker({"tool": tool, "arguments": dict(arguments)}))

    @staticmethod
    def _fingerprint(path):
        if not isinstance(path, str) or not path:
            raise ComputerLoopError("Screenshot path is required for visual verification.")
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    hasher.update(chunk)
        except (OSError, TypeError) as exc:
            raise ComputerLoopError("Unable to fingerprint screenshot.") from exc
        return hasher.hexdigest()

    @staticmethod
    def _action_signature(action):
        return json.dumps(
            {"tool": action["tool"], "arguments": action["arguments"]},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _observe(self):
        geometry = self._screen_geometry()
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
        try:
            fingerprint = self._fingerprint(path)
        except ComputerLoopError as exc:
            self._cleanup(path)
            return None, {"ok": False, "status": "observation_failed", "error": str(exc)}
        return {"image_path": path, "screen": geometry, "fingerprint": fingerprint}, None

    @staticmethod
    def _validate_visual_state(decision):
        state = decision.get("visual_state")
        if state is None:
            return {}
        if not isinstance(state, dict):
            raise ComputerLoopError("visual_state must be an object.")
        allowed = {"summary", "target_visible", "completed", "blocked"}
        if set(state) - allowed:
            raise ComputerLoopError("visual_state contains unsupported fields.")
        summary = state.get("summary", "")
        if not isinstance(summary, str) or len(summary) > 1000:
            raise ComputerLoopError("visual_state summary must be a string of at most 1000 characters.")
        for key in ("target_visible", "completed", "blocked"):
            if key in state and not isinstance(state[key], bool):
                raise ComputerLoopError("visual_state boolean fields must be boolean.")
        return dict(state)

    def _validate(self, decision):
        if not isinstance(decision, dict):
            raise ComputerLoopError("Computer decision must be an object.")
        if decision.get("done") is True:
            return None
        visual_state = self._validate_visual_state(decision)
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
        return {"tool": tool, "arguments": arguments, "approved": approved, "visual_state": visual_state}

    def run(self, decide: Callable, initial_image=None):
        if not callable(decide):
            raise ComputerLoopError("decide must be callable.")

        observation = None
        if initial_image:
            observation = {
                "image_path": initial_image,
                "screen": self._screen_geometry(),
                "fingerprint": self._fingerprint(initial_image),
            }
        history = []
        last_action_signature = None
        last_before_fingerprint = None
        repeated_action_count = 0
        for iteration in range(1, self.max_iterations + 1):
            if not observation:
                observation, failure = self._observe()
                if failure:
                    return {"ok": False, "iterations": iteration - 1, "history": history, **failure}

            decision = decide(observation, list(history))
            action = self._validate(decision)
            if action is not None:
                self._validate_coordinates(action["tool"], action["arguments"], observation["screen"])
            if action is None:
                return {
                    "ok": True, "status": "completed",
                    "iterations": iteration - 1, "history": history,
                }

            action_signature = self._action_signature(action)
            if (
                action_signature == last_action_signature
                and observation["fingerprint"] == last_before_fingerprint
            ):
                repeated_action_count += 1
            else:
                repeated_action_count = 1
            if repeated_action_count >= 2:
                self._cleanup(observation["image_path"])
                return {
                    "ok": False,
                    "status": "stagnated",
                    "iterations": iteration - 1,
                    "error": "The same desktop action was proposed repeatedly without a visual state change.",
                    "history": history,
                    "screen": observation["screen"],
                }

            before_fingerprint = observation["fingerprint"]
            last_action_signature = action_signature
            last_before_fingerprint = before_fingerprint
            result = self.registry.execute(
                action["tool"], action["arguments"], approved=action["approved"]
            )
            event = {"iteration": iteration, "action": {k: action[k] for k in ("tool", "arguments", "approved")}, "result": result, "visual_state": action["visual_state"]}
            history.append(event)
            if not result.get("ok"):
                self._cleanup(observation["image_path"])
                return {
                    "ok": False, "status": "action_failed", "iterations": iteration,
                    "error": result.get("error", "Computer action failed."), "history": history,
                    "screen": observation["screen"],
                }

            self._cleanup(observation["image_path"])
            observation, failure = self._observe()
            if failure:
                return {"ok": False, "iterations": iteration, "history": history, **failure}
            event["visual_verification"] = {
                "before": before_fingerprint,
                "after": observation["fingerprint"],
                "changed": before_fingerprint != observation["fingerprint"],
            }

        if observation:
            self._cleanup(observation["image_path"])
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
