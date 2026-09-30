import unittest

from app.permissions import Permission, PermissionManager


class PermissionTests(unittest.TestCase):
    def test_ungranted_permission_requires_approval(self):
        manager = PermissionManager()
        decision = manager.decide(Permission.TERMINAL_EXECUTE)
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

    def test_explicit_approval_allows_once(self):
        manager = PermissionManager()
        decision = manager.decide(Permission.GIT_COMMIT, approved=True)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)
        self.assertFalse(manager.has(Permission.GIT_COMMIT))

    def test_grant_and_revoke(self):
        manager = PermissionManager()
        manager.grant(Permission.WORKSPACE_READ)
        self.assertTrue(manager.has(Permission.WORKSPACE_READ))
        self.assertTrue(manager.decide(Permission.WORKSPACE_READ).allowed)
        manager.revoke(Permission.WORKSPACE_READ)
        self.assertFalse(manager.has(Permission.WORKSPACE_READ))


if __name__ == "__main__":
    unittest.main()
