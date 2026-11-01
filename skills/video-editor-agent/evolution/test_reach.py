"""No network, installation, credentials or paid tools."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reach
from learn import Learning, read, write


class ReachTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        write(self.root / "learning" / "config.json", {
            "schema_version": 1, "repository": "example/test", "branch": "main"})
        self.engine = Learning(self.root / "learning")
        self.engine.begin(self.project, "Synthetic niche", "en", "US", "short")

    def collect(self, query="test query"):
        return reach.collect(self.project, "youtube", query, engine=self.engine)

    def test_query_never_becomes_shell_or_flags(self):
        query = "--bad-option ; touch injected"
        cmd = reach.command("youtube", query, 5)
        self.assertEqual(cmd[-2:], ["--", query])
        with self.assertRaises(ValueError):
            reach.command("youtube", query, 21)

    def test_uninstalled_records_gap_without_install(self):
        with patch.object(reach.shutil, "which", return_value=None), patch.object(reach.subprocess, "run") as run:
            result = self.collect()
        self.assertEqual(result["status"], "unavailable")
        run.assert_not_called()

    def test_success_checkpoint_and_no_repeated_search(self):
        response = {"schema_version": 1, "channel": "youtube", "action": "search", "ok": True,
                    "items": [{"title": "synthetic result"}]}
        with patch.object(reach.shutil, "which", return_value="/test/agent-reach"), patch.object(
                reach.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(response), "")) as run:
            first = self.collect(); second = self.collect()
        self.assertEqual(first["status"], "ok")
        self.assertTrue(second["cached"])
        self.assertEqual(run.call_count, 1)
        self.assertIs(run.call_args.kwargs["shell"], False)

    def test_schema_failure_not_retried_or_logged_as_success(self):
        with patch.object(reach.shutil, "which", return_value="/test/agent-reach"), patch.object(
                reach.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"schema_version":2}', "secret")) as run:
            first = self.collect(); second = self.collect()
        self.assertEqual(first["status"], "error")
        self.assertTrue(second["cached"])
        self.assertNotIn("secret", json.dumps(read(self.project / first["file"])))
        self.assertEqual(run.call_count, 1)

    def test_timeout_is_checkpointed_without_retry(self):
        with patch.object(reach.shutil, "which", return_value="/test/agent-reach"), patch.object(
                reach.subprocess, "run", side_effect=subprocess.TimeoutExpired("agent-reach", 45)) as run:
            self.assertEqual(self.collect()["status"], "error")
            self.assertTrue(self.collect()["cached"])
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
