"""Offline tests for the viral-blueprint module: selection by views, dissection, originality checks.
Synthetic fixtures only; no vidIQ calls."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "skills/viral-blueprint/scripts/blueprint.py"
spec = importlib.util.spec_from_file_location("blueprint", PATH)
bp = importlib.util.module_from_spec(spec)
sys.modules["blueprint"] = bp
spec.loader.exec_module(bp)

NOW = "2026-11-08T00:00:00+00:00"
SOURCE_TEXT = ("Why do strong men stay silent while weak men talk loudly? By the end of this video you will "
               "understand the first rule of power. First, silence hides your next move. But most people never "
               "learn this. Second, silence makes others reveal themselves. Subscribe if this hit you.")


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = bp.main(argv)
    return code, out.getvalue()


class ViralBlueprintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        outliers = {"videos": [
            {"videoId": "AAAAAAAAAAA", "title": "Why Strong Men Stay Silent", "channelId": "UC1", "channelTitle": "One",
             "publishedAt": "2026-09-01T00:00:00Z", "viewCount": 900000, "duration": "PT8M10S"},
            {"videoId": "BBBBBBBBBBB", "title": "7 Rules of Silent Power", "channelId": "UC1", "channelTitle": "One",
             "publishedAt": "2026-09-05T00:00:00Z", "viewCount": 800000, "duration": "PT9M"},
            {"videoId": "CCCCCCCCCCC", "title": "Silence Is Power (Stoic)", "channelId": "UC2", "channelTitle": "Two",
             "publishedAt": "2026-08-01T00:00:00Z", "viewCount": 500000, "duration": "PT45S"},
            {"videoId": "DDDDDDDDDDD", "title": "My own upload", "channelId": "UCME", "channelTitle": "Me",
             "publishedAt": "2026-08-01T00:00:00Z", "viewCount": 9000000, "duration": "PT10M"},
        ]}
        refresh = [{"id": "EEEEEEEEEEE", "title": "Be Quiet, Win More", "channelId": "UC3", "channelTitle": "Three",
                    "publishedAt": "2026-10-01T00:00:00Z", "viewCount": "650,000", "duration": "PT12M",
                    "description": "The quiet man wins. Learn the psychology of silence and power today.\n0:00 Intro\n#stoic #silence",
                    "tags": ["silence", "stoicism", "power"]},
                   {"id": "AAAAAAAAAAA", "viewCount": 950000, "tags": ["silence", "power", "stoic"],
                    "description": "Silence is the weapon nobody teaches you to use in this world. #mindset"}]
        (self.tmp / "outliers.json").write_text(json.dumps(outliers))
        (self.tmp / "refresh.json").write_text(json.dumps(refresh))
        (self.tmp / "transcript.json").write_text(json.dumps({"segments": [
            {"start": i * 20, "text": chunk} for i, chunk in enumerate(SOURCE_TEXT.split(". "))]}))
        self.sel = self.tmp / "viral/selection.json"
        code, _ = run(["select", str(self.tmp / "outliers.json"), str(self.tmp / "refresh.json"), "--format", "long",
                       "--exclude-channel", "@me", "--exclude-channel", "UCME", "--now", NOW, "-o", str(self.sel)])
        self.assertEqual(code, 0)

    def test_select_ranks_by_views_one_per_channel_and_excludes_short_and_own(self):
        data = json.loads(self.sel.read_text())
        self.assertEqual(data["picks"], ["AAAAAAAAAAA", "EEEEEEEEEEE"])  # B dropped by per-channel cap
        by_id = {c["id"]: c for c in data["candidates"]}
        self.assertEqual(by_id["AAAAAAAAAAA"]["viewCount"], 950000)  # refreshed stats win
        self.assertIn("own channel", by_id["DDDDDDDDDDD"]["excluded"])
        self.assertTrue(any("format" in r for r in by_id["CCCCCCCCCCC"]["excluded"]))
        self.assertEqual(data["cohort"]["rankingMetric"], "viewCount")

    def dissect(self):
        out = self.tmp / "viral/blueprint.json"
        code, _ = run(["dissect", str(self.sel), "--video", "AAAAAAAAAAA", "--transcript", str(self.tmp / "transcript.json"), "-o", str(out)])
        self.assertEqual(code, 0)
        return out

    def test_dissect_reports_structure(self):
        b = json.loads(self.dissect().read_text())
        self.assertEqual(len(b["script"]["beats"]), 10)
        self.assertTrue(b["script"]["hook"]["opensWithQuestion"])
        self.assertGreaterEqual(b["script"]["devices"]["list"], 2)
        self.assertIn("opens_why", b["title"]["patterns"])
        self.assertEqual(b["metadata"]["tags"], ["silence", "power", "stoic"])
        self.assertTrue((self.tmp / "viral/blueprint.md").exists())

    def test_check_blocks_copied_script_and_title(self):
        out = self.dissect()
        script = self.tmp / "copy.md"
        script.write_text("## Chapter\n" + SOURCE_TEXT)
        code, text = run(["check", str(out), "--script", str(script), "--title", "Why Strong Men Stay Silent!"])
        self.assertEqual(code, 1)
        self.assertIn("consecutive words copied", text)
        self.assertIn("similar to the source title", text)

    def test_check_passes_original_rewrite(self):
        out = self.dissect()
        script = self.tmp / "new.md"
        script.write_text("## The Quiet Edge\nWhat if the loudest person in the room is the one losing? "
                          "Stay with me, because the third idea changes how you argue forever. "
                          "One: a closed mouth keeps your plan invisible. Two: a pause pulls the truth out of others. "
                          "Three: calm turns pressure into leverage.\n")
        upload = self.tmp / "upload.json"
        upload.write_text(json.dumps({"title": "The Quiet Man Always Wins: 3 Rules of Calm Power",
                                      "description": "Calm beats loud. Three rules for using a pause as leverage.\n#mindset #discipline",
                                      "tags": ["calm power", "discipline", "silence"]}))
        code, text = run(["check", str(out), "--script", str(script), "--upload", str(upload)])
        self.assertEqual(code, 0, text)

    def test_check_detects_copied_japanese_by_characters(self):
        jp = "静かな男が勝つ理由を知っていますか。最後まで見れば力の第一法則がわかります。"
        b = json.loads(self.dissect().read_text())
        b["sourceTranscript"] = jp
        path = self.tmp / "jp.json"
        path.write_text(json.dumps(b, ensure_ascii=False))
        script = self.tmp / "jp.md"
        script.write_text("最後まで見れば力の第一法則がわかります。今日から試してください。", encoding="utf-8")
        code, text = run(["check", str(path), "--script", str(script)])
        self.assertEqual(code, 1)
        self.assertIn("characters copied", text)


if __name__ == "__main__":
    unittest.main()
