"""Exercise native production gates without network, generation or valid media."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOME = Path(__file__).resolve().parent


class NativeGateTests(unittest.TestCase):
    def test_native_production_rejects_unapplied_learning(self):
        config_path = HOME / "config.json"
        if not config_path.exists():
            self.skipTest("Run this integration test inside an upgraded repository")
        config = json.loads(config_path.read_text())
        name = config["repository"].split("/")[-1]
        repo = HOME.parents[2] if name == "chatgpt-video-editor-agent" else HOME.parent
        spec = importlib.util.spec_from_file_location("native_learning", HOME / "learn.py")
        learning = importlib.util.module_from_spec(spec); spec.loader.exec_module(learning)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "production"
            scope = config.get("fixed_scope", {})
            learning.Learning(HOME).begin(project, "Synthetic gate test", scope.get("language", "en"),
                scope.get("market", "US"), scope.get("format", "short"))
            artifact = project / "artifact.json"
            artifact.write_text("{}")
            if name in {"japanese-shorts-agent", "korean-shorts-agent"}:
                module = "jp_shorts" if name.startswith("japanese") else "ko_shorts"
                command = ["-m", module, "speech-plan", str(project), "--voice", "synthetic-voice"]
            elif name == "elevenlabs-claudecode":
                command = ["-m", "elmarketing", "render", str(artifact), "--output", str(project / "out.mp4")]
            elif name == "chatgpt-video-editor-agent":
                command = [str(HOME.parent / "scripts/media.py"), "render", str(artifact), "--out", str(project / "out.mp4")]
            elif name == "ai-drama-series-agent":
                command = ["scripts/drama.py", "assemble", str(artifact)]
            else:
                # Advance only the local ingest checkpoint; the configured edit must not execute.
                cli = [sys.executable, str(repo / "tools/editor/editor.py"), "project"]
                source = project / "source.mov"; source.write_bytes(b"synthetic source identity")
                for argv in (["init", str(project), "--source", str(source)],
                             ["checkpoint", str(project), "ingest", "--artifact", str(source)]):
                    setup = subprocess.run(cli + argv, cwd=repo, capture_output=True, text=True, timeout=10)
                    self.assertEqual(setup.returncode, 0, setup.stderr)
                command = ["tools/editor/editor.py", "project", "resume", str(project), "--run"]
            result = subprocess.run([sys.executable, *command], cwd=repo, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Learning not applied", result.stderr)
            self.assertFalse((project / "out.mp4").exists())


if __name__ == "__main__":
    unittest.main()
