# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""The commit-message hook is enforced, not merely documented.

`.githooks/commit-msg` rejects any subject that is not Conventional Commits. It
lives in the repository but is wired up by `core.hooksPath`, which is local Git
config and cannot be committed -- so a fresh clone carries the hook with nothing
pointing at it, and every commit passes unchecked without saying so. That is the
same failure shape as the cjxl-gated tests, so these tests exist to make the gap
loud instead of silent.

None of this needs `cjxl`, so it runs in the stripped environment too.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, ".githooks", "commit-msg")

SETUP = "git config core.hooksPath .githooks"


class CommitHookBehaviour(unittest.TestCase):
    """The hook accepts conforming subjects and rejects everything else."""

    def _check(self, message):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write(message)
            path = handle.name
        try:
            # Run the hook as an executable, exactly as Git does, so the shebang
            # and the executable bit are covered rather than bypassed.
            return subprocess.run(
                [HOOK, path], capture_output=True, text=True
            ).returncode
        finally:
            os.unlink(path)

    def assertAccepted(self, message):
        self.assertEqual(
            self._check(message), 0, "expected %r to be accepted" % message
        )

    def assertRejected(self, message):
        self.assertEqual(
            self._check(message), 1, "expected %r to be rejected" % message
        )

    def test_accepts_a_conforming_subject(self):
        self.assertAccepted(
            "fix: treat output-name collisions the way readers resolve them\n"
        )

    def test_accepts_a_scope(self):
        self.assertAccepted("feat(cli): add --dry-run\n")

    def test_accepts_every_canonical_type(self):
        for kind in ("feat", "fix", "chore", "refactor", "docs", "test", "perf"):
            with self.subTest(kind=kind):
                self.assertAccepted("%s: change something\n" % kind)

    def test_accepts_the_types_bmad_build_emits(self):
        # bmad-build derives the commit type from plan frontmatter, whose values
        # are feature/bugfix/refactor/chore. Enforcing only the canonical set
        # would make it fail its own commit.
        for kind in ("feature", "bugfix"):
            with self.subTest(kind=kind):
                self.assertAccepted("%s: change something\n" % kind)

    def test_rejects_a_missing_type_prefix(self):
        self.assertRejected("Add cbx-jackal\n")

    def test_rejects_a_capitalised_subject(self):
        self.assertRejected("fix: Treat output-name collisions\n")

    def test_rejects_a_capitalised_imperative(self):
        self.assertRejected("Treat output-name collisions the way readers resolve them\n")

    def test_rejects_an_unknown_type(self):
        self.assertRejected("wip: something in progress\n")

    def test_rejects_an_empty_subject(self):
        self.assertRejected("fix:\n")

    def test_exempts_merge_commits(self):
        self.assertAccepted("Merge branch 'feat/x' into main\n")

    def test_exempts_reverts_and_autosquash(self):
        for prefix in ('Revert "feat: x"', "fixup! feat: x", "squash! feat: x"):
            with self.subTest(prefix=prefix):
                self.assertAccepted(prefix + "\n")

    def test_accepts_an_empty_message(self):
        self.assertAccepted("")

    def test_accepts_a_comment_only_message(self):
        self.assertAccepted("# on its way\n\n")

    def test_rejection_explishes_itself(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("Not conventional\n")
            path = handle.name
        try:
            result = subprocess.run([HOOK, path], capture_output=True, text=True)
        finally:
            os.unlink(path)
        self.assertIn("conventionalcommits", result.stderr)
        self.assertIn("--no-verify", result.stderr)


class HookIsInstalled(unittest.TestCase):
    """The hook file is wired up, which a clone cannot inherit."""

    def test_hooks_path_points_at_the_hook(self):
        try:
            result = subprocess.run(
                ["git", "config", "--get", "core.hooksPath"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("git is not available")

        if result.returncode != 0:
            self.fail(
                "core.hooksPath is unset, so no commit is checked. The hook is "
                "committed but this setting is local Git config and cannot be. "
                "Run: %s" % SETUP
            )

        configured = result.stdout.strip().replace("\\", "/")
        self.assertTrue(
            configured.endswith(".githooks"),
            "core.hooksPath is %r, which does not point at %s. Run: %s"
            % (configured, HOOK, SETUP),
        )


if __name__ == "__main__":
    unittest.main()