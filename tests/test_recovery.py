import unittest

from app.recovery import RecoveryCoordinator


class RecoveryTests(unittest.TestCase):
    def test_retries_failed_verification_until_success(self):
        checks = [{"ok": False}, {"ok": False}, {"ok": True}]
        repairs = []

        def verify():
            return checks.pop(0)

        def repair(result):
            repairs.append(result)
            return {"ok": True}

        result = RecoveryCoordinator(verify, repair, max_attempts=3).run()

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(repairs), 2)

    def test_stops_at_retry_limit(self):
        result = RecoveryCoordinator(lambda: {"ok": False}, lambda _: {"ok": True}, max_attempts=2).run()
        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 2)

    def test_repair_failure_stops_immediately(self):
        result = RecoveryCoordinator(lambda: {"ok": False}, lambda _: {"ok": False, "error": "repair failed"}, max_attempts=3).run()
        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.final_result["error"], "repair failed")


if __name__ == "__main__":
    unittest.main()
