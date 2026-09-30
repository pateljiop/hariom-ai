"""Bounded verification recovery coordinator."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryResult:
    ok: bool
    attempts: int
    final_result: dict


class RecoveryCoordinator:
    def __init__(self, verify, repair, max_attempts=3):
        if not callable(verify) or not callable(repair):
            raise ValueError("verify and repair must be callable.")
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.verify = verify
        self.repair = repair
        self.max_attempts = max_attempts

    def run(self):
        last = self.verify()
        attempts = 0
        while not last.get("ok") and attempts < self.max_attempts:
            attempts += 1
            repair_result = self.repair(last)
            if not repair_result.get("ok"):
                return RecoveryResult(False, attempts, repair_result)
            last = self.verify()
        return RecoveryResult(bool(last.get("ok")), attempts, last)
