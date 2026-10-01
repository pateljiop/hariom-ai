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

    def test_task_bound_approval_overrides_persistent_grant(self):
        manager = PermissionManager(grants=(Permission.TERMINAL_EXECUTE,))
        decision = manager.decide(Permission.TERMINAL_EXECUTE, approved=True, task_id="task-1", tool="terminal.run")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)
        self.assertEqual(decision.reason, "bound_approval_required")

    def test_signed_approval_token_is_exact_and_one_time(self):
        manager = PermissionManager()
        args = {"path": "x.txt", "content": "ok"}
        token = manager.issue_approval_token(
            task_id="task-1", tool="workspace.write",
            permission=Permission.WORKSPACE_WRITE, arguments=args, ttl_seconds=60
        )
        decision = manager.decide(
            Permission.WORKSPACE_WRITE, task_id="task-1",
            tool="workspace.write", arguments=args, approval_token=token
        )
        self.assertTrue(decision.allowed)
        replay = manager.decide(
            Permission.WORKSPACE_WRITE, task_id="task-1",
            tool="workspace.write", arguments=args, approval_token=token
        )
        self.assertFalse(replay.allowed)
        self.assertEqual(replay.reason, "approval_consumed")

    def test_signed_approval_token_rejects_argument_changes(self):
        manager = PermissionManager()
        token = manager.issue_approval_token(
            task_id="task-1", tool="workspace.write",
            permission=Permission.WORKSPACE_WRITE,
            arguments={"path": "x.txt", "content": "approved"}, ttl_seconds=60
        )
        decision = manager.decide(
            Permission.WORKSPACE_WRITE, task_id="task-1",
            tool="workspace.write",
            arguments={"path": "x.txt", "content": "changed"},
            approval_token=token
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "approval_arguments_mismatch")

    def test_grant_and_revoke(self):
        manager = PermissionManager()
        manager.grant(Permission.WORKSPACE_READ)
        self.assertTrue(manager.has(Permission.WORKSPACE_READ))
        self.assertTrue(manager.decide(Permission.WORKSPACE_READ).allowed)
        manager.revoke(Permission.WORKSPACE_READ)
        self.assertFalse(manager.has(Permission.WORKSPACE_READ))


if __name__ == "__main__":
    unittest.main()
