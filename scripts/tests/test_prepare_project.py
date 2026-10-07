"""Bundled projects discover their legacy folder without a fixed system name."""

from pathlib import Path
import tempfile
import unittest

from scripts import prepare_project


class PrepareProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "nvi-code-modernization").mkdir()

    def test_discovers_single_legacy_folder_and_is_idempotent(self):
        source = self.root / "legacy_app"
        source.mkdir()
        (source / "main.txt").write_text("original", encoding="utf-8")
        system, link = prepare_project.prepare(self.root)
        self.assertEqual(system, "legacy_app")
        self.assertEqual((link / "main.txt").read_text(encoding="utf-8"), "original")
        self.assertTrue((self.root / "modernized").is_dir())
        self.assertEqual(prepare_project.prepare(self.root), (system, link))

    def test_requires_selection_when_multiple_sources_exist(self):
        (self.root / "one").mkdir()
        (self.root / "two").mkdir()
        with self.assertRaisesRegex(ValueError, "found: one, two"):
            prepare_project.prepare(self.root)
        system, _ = prepare_project.prepare(self.root, "two")
        self.assertEqual(system, "two")

    def test_rejects_conflicting_legacy_alias(self):
        (self.root / "app").mkdir()
        (self.root / "legacy" / "app").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "points elsewhere"):
            prepare_project.prepare(self.root)

    def test_rejects_workflow_directory_as_source(self):
        with self.assertRaisesRegex(ValueError, "legacy source folder"):
            prepare_project.prepare(self.root, "nvi-code-modernization")


if __name__ == "__main__":
    unittest.main()
