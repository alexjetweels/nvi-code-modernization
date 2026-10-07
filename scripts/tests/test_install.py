"""The installer must keep the legacy tree separate and preserve workspace files."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts import install as installer


class InstallWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "old app"
        self.source.mkdir()
        (self.source / "app.txt").write_text("legacy\n", encoding="utf-8")
        self.workspace = self.root / "migration work"

    def run_install(self, hosts=("all",), replace=False):
        args = type("Args", (), {"workspace": str(self.workspace), "source": str(self.source),
                                   "system": "billing", "host": list(hosts), "replace": replace})()
        return installer.install(args)

    def test_all_hosts_install_into_separate_workspace(self):
        self.assertEqual(self.run_install(), 0)
        self.assertEqual((self.source / "app.txt").read_text(encoding="utf-8"), "legacy\n")
        self.assertEqual((self.workspace / "legacy" / "billing" / "app.txt").read_text(encoding="utf-8"), "legacy\n")
        self.assertTrue((self.workspace / "plugins" / "nvi-code-modernization" / "plugin.json").is_file())
        self.assertTrue((self.workspace / ".agents" / "skills" / "nvi-code-modernization" / "SKILL.md").is_file())
        self.assertTrue((self.workspace / ".github" / "prompts" / "nvi-modernize.prompt.md").is_file())
        self.assertTrue((self.workspace / ".claude-plugin" / "marketplace.json").is_file())
        self.assertIn("nvi-code-modernization@nvi-code-modernization-local", (self.workspace / ".codex" / "config.toml").read_text(encoding="utf-8"))
        state = json.loads((self.workspace / ".modernization" / "install.json").read_text(encoding="utf-8"))
        self.assertEqual(set(state["hosts"]), set(installer.HOSTS))

    def test_reinstall_adds_host_without_replacing_existing_work(self):
        self.run_install(("codex",))
        note = self.workspace / "analysis" / "billing" / "PREFLIGHT.md"
        note.parent.mkdir(parents=True)
        note.write_text("keep me", encoding="utf-8")
        self.run_install(("antigravity",))
        self.assertEqual(note.read_text(encoding="utf-8"), "keep me")
        self.assertTrue((self.workspace / ".agents" / "workflows" / "nvi-modernize.md").exists())
        self.assertEqual(self.run_install(("codex",), replace=True), 0)
        self.assertEqual(note.read_text(encoding="utf-8"), "keep me")

    def test_rejects_overlapping_workspace_and_source(self):
        with self.assertRaises(installer.InstallError):
            installer.assert_workspace_separate(self.source / "migration", self.source)
        with self.assertRaises(installer.InstallError):
            installer.assert_workspace_separate(self.root, self.source)

    def test_does_not_replace_unmanaged_plugin(self):
        plugin = self.workspace / "plugins" / "nvi-code-modernization"
        plugin.mkdir(parents=True)
        (plugin / "important.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(installer.InstallError):
            self.run_install(("codex",), replace=True)
        self.assertEqual((plugin / "important.txt").read_text(encoding="utf-8"), "keep")

    @unittest.skipIf(os.name == "nt", "creating test symlinks requires Windows developer mode")
    def test_rejects_generated_file_link_outside_workspace(self):
        outside = self.root / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        path = self.workspace / ".github" / "prompts" / "nvi-modernize.prompt.md"
        path.parent.mkdir(parents=True)
        path.symlink_to(outside)
        with self.assertRaisesRegex(installer.InstallError, "escapes through a link"):
            self.run_install(("copilot-vscode",))
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
