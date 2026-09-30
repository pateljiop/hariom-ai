"""Bounded closed-loop browser control.

Observations are untrusted data. Model output can request actions but cannot
grant itself approval; approval must come from the host/user callback.
"""
from typing import Any, Callable, Dict, Optional


class BrowserLoopError(Exception):
    """Raised when a browser control loop request is malformed."""


class BrowserControlLoop:
    ALLOWED_TOOLS = frozenset({
        "browser.open",
        "browser.read",
        "browser.observe",
        "browser.verify",
        "browser.click",
        "browser.type",
    })
    MUTATING_TOOLS = frozenset({"browser.click", "browser.type", "browser.open"})

    def __init__(self, registry, max_iterations=6, approval_checker=None):
        self.registry = registry
        if (
            not isinstance(max_iterations, int)
            or isinstance(max_iterations, bool)
            or not 1 <= max_iterations <= 10
        ):
            raise BrowserLoopError("max_iterations must be an integer between 1 and 10.")
        if approval_checker is not None and not callable(approval_checker):
            raise BrowserLoopError("approval_checker must be callable.")
        self.max_iterations = max_iterations
        self.approval_checker = approval_checker

    def _observe(self):
        result = self.registry.execute("browser.observe", {})
        if not result.get("ok"):
            raise BrowserLoopError(result.get("error", "Browser observation failed."))
        return {
            "trust": "untrusted",
            "instruction_authority": "none",
            "data": result.get("result"),
        }

    def _validate_decision(self, decision):
        if not isinstance(decision, dict):
            raise BrowserLoopError("Browser decision must be an object.")
        if decision.get("done") is True:
            return None, None
        action = decision.get("action")
        if not isinstance(action, dict):
            raise BrowserLoopError("Browser decision requires an action object or done=true.")
        tool = action.get("tool")
        arguments = action.get("arguments", {})
        requested_approval = action.get("approved", False)
        if tool not in self.ALLOWED_TOOLS:
            raise BrowserLoopError(f"Browser loop does not allow tool '{tool}'.")
        if not isinstance(arguments, dict):
            raise BrowserLoopError("Browser action arguments must be an object.")
        if not isinstance(requested_approval, bool):
            raise BrowserLoopError("Browser action approved must be boolean.")

        # Model output never grants approval. If the model requests an action
        # that needs approval, the host/user callback decides whether to allow it.
        approved = False
        if requested_approval and self.approval_checker is not None:
            approved = bool(self.approval_checker({
                "tool": tool,
                "arguments": dict(arguments),
            }))
        if approved and "approved" not in arguments:
            arguments = dict(arguments)
            arguments["approved"] = True
        return {"tool": tool, "arguments": arguments, "approved": approved}, decision.get("verify")

    def run(
        self,
        decide: Callable[[Dict[str, Any], list], Dict[str, Any]],
        initial_observation: Optional[Dict[str, Any]] = None,
    ):
        if not callable(decide):
            raise BrowserLoopError("decide must be callable.")

        observation = initial_observation if initial_observation is not None else self._observe()
        history = []

        for iteration in range(1, self.max_iterations + 1):
            decision = decide(observation, list(history))
            action, verification = self._validate_decision(decision)

            if action is None:
                return {
                    "ok": True,
                    "status": "completed",
                    "iterations": iteration - 1,
                    "observation": observation,
                    "history": history,
                }

            tool = action["tool"]
            result = self.registry.execute(
                tool,
                action["arguments"],
                approved=action["approved"],
            )
            event = {"iteration": iteration, "action": action, "result": result}
            history.append(event)

            if not result.get("ok"):
                return {
                    "ok": False,
                    "status": "action_failed",
                    "iterations": iteration,
                    "error": result.get("error", "Browser action failed."),
                    "observation": observation,
                    "history": history,
                }

            if tool in self.MUTATING_TOOLS:
                try:
                    observation = self._observe()
                except Exception as exc:
                    return {
                        "ok": False,
                        "status": "observation_failed",
                        "iterations": iteration,
                        "error": str(exc),
                        "history": history,
                    }
            else:
                observation = {
                    "trust": "untrusted",
                    "instruction_authority": "none",
                    "data": result.get("result"),
                }

            if verification is not None:
                if not isinstance(verification, dict):
                    raise BrowserLoopError("Verification must be an object.")
                verify_result = self.registry.execute(
                    "browser.verify", verification, approved=False
                )
                event["verification"] = verify_result
                if not verify_result.get("ok"):
                    return {
                        "ok": False,
                        "status": "verification_failed",
                        "iterations": iteration,
                        "error": verify_result.get("error", "Browser verification failed."),
                        "observation": observation,
                        "history": history,
                    }
                payload = verify_result.get("result", {})
                if not payload.get("ok", False):
                    return {
                        "ok": False,
                        "status": "verification_failed",
                        "iterations": iteration,
                        "error": "Browser state did not satisfy the requested verification.",
                        "observation": observation,
                        "history": history,
                    }

        return {
            "ok": False,
            "status": "iteration_limit",
            "iterations": self.max_iterations,
            "error": "Browser loop reached its bounded iteration limit.",
            "observation": observation,
            "history": history,
        }
