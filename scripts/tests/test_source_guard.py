import os
from pathlib import Path
import tempfile
import unittest

from scripts import source_guard
from scripts import proof_pack


class SourceGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.source = self.workspace / "legacy" / "billing"
        self.source.mkdir(parents=True)
        (self.source / "a.txt").write_text("old", encoding="utf-8")

    def test_detects_same_size_change_and_added_file(self):
        result = source_guard.snapshot(self.workspace, "billing")
        self.assertEqual(result["state"], "clean")
        self.assertEqual(source_guard.verify(self.workspace, "billing")["state"], "clean")
        (self.source / "a.txt").write_text("new", encoding="utf-8")
        (self.source / "b.txt").write_text("added", encoding="utf-8")
        changed = source_guard.verify(self.workspace, "billing")
        self.assertEqual(changed["state"], "changed")
        self.assertEqual(changed["files"], ["a.txt", "b.txt"])

    def test_unknown_when_snapshot_missing_or_corrupt(self):
        self.assertEqual(source_guard.verify(self.workspace, "billing")["state"], "unknown")
        source_guard.snapshot(self.workspace, "billing")
        saved = self.workspace / "analysis" / "billing" / "SOURCE_SNAPSHOT.json"
        saved.write_text("{}", encoding="utf-8")
        self.assertEqual(source_guard.verify(self.workspace, "billing")["state"], "unknown")

    def test_snapshot_rerun_preserves_original_baseline(self):
        source_guard.snapshot(self.workspace, "billing")
        saved = self.workspace / "analysis" / "billing" / "SOURCE_SNAPSHOT.json"
        baseline = saved.read_bytes()
        self.assertEqual(source_guard.snapshot(self.workspace, "billing")["state"], "clean")
        self.assertEqual(saved.read_bytes(), baseline)
        (self.source / "a.txt").write_text("new", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "preserve the original baseline"):
            source_guard.snapshot(self.workspace, "billing")
        self.assertEqual(saved.read_bytes(), baseline)

    def test_proof_pack_uses_snapshot_when_available(self):
        source_guard.snapshot(self.workspace, "billing")
        adir = self.workspace / "analysis" / "billing"
        (self.source / "a.txt").write_text("new", encoding="utf-8")
        result = proof_pack.source_check(str(self.workspace), "billing", str(adir))
        self.assertEqual(result["state"], "changed")
        self.assertEqual(result["method"], "SHA-256 snapshot")
        self.assertEqual(result["files"], ["a.txt"])

    @unittest.skipIf(os.name == "nt", "creating source symlinks requires Windows developer mode")
    def test_symlink_target_is_recorded_without_following_it(self):
        outside = self.workspace / "elsewhere"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret", encoding="utf-8")
        (self.source / "other").symlink_to(outside, target_is_directory=True)
        source_guard.snapshot(self.workspace, "billing")
        self.assertEqual(source_guard.verify(self.workspace, "billing")["state"], "clean")
        (outside / "secret.txt").write_text("changed", encoding="utf-8")
        self.assertEqual(source_guard.verify(self.workspace, "billing")["state"], "clean")


if __name__ == "__main__":
    unittest.main()
