#!/usr/bin/env python3
"""Offline regression tests. Creates synthetic media only in temporary directories."""
import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import media
import project


class ProjectTests(unittest.TestCase):
    def test_split_preserves_exact_text(self):
        text = "First sentence. Another thought.\n\nNext paragraph with an apostrophe: don't.\n"
        chunks = project.split_text(text, 28)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 28 for c in chunks))
        with self.assertRaises(ValueError):
            project.split_text("x" * 40, 20)

    def test_changed_script_invalidates_narration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            project.init(root, "Fixture")
            script, audio = root / "script.txt", root / "audio.txt"
            script.write_text("Approved script"); audio.write_text("Audio stand-in")
            with self.assertRaises(ValueError):
                project.record(root, "script", script, True)
            project.record(root, "script", script, True, "User approved fixture")
            project.record(root, "narration", audio, True, "User approved fixture")
            self.assertTrue(project.status(root)["stages"]["narration"]["approved"])
            script.write_text("Changed script")
            self.assertEqual(project.status(root)["stages"]["narration"]["status"], "stale")
            project.record(root, "script", script)
            self.assertFalse(project.status(root)["stages"]["narration"]["approved"])

    def test_cost_estimate_not_charge_and_preserves_unit(self):
        with tempfile.TemporaryDirectory() as d:
            project.init(d, "Costs")
            args = argparse.Namespace(id="n1", provider="ElevenLabs", unit="elevenlabs_credit",
                estimated=200, actual=None, refunded=None, status="failed", job_id="fixture", evidence=None)
            row = project.cost(d, args)
            self.assertIsNone(row["actual"])
            self.assertIsNone(row["refunded"])
            args.actual = 200
            with self.assertRaises(ValueError):
                project.cost(d, args)
            args.evidence = "Synthetic receipt fixture"
            self.assertEqual(project.cost(d, args)["actual"], 200)
            args.unit = "USD"
            with self.assertRaises(ValueError):
                project.cost(d, args)


class CaptionTests(unittest.TestCase):
    def test_caption_limits_and_silence(self):
        words = [{"word": "word", "start": i*.3, "end": i*.3+.2} for i in range(60)]
        cues = media.caption_cues(words)
        self.assertEqual(" ".join(c["text"].replace("\n"," ") for c in cues), " ".join(["word"]*60))
        self.assertTrue(all(len(c["text"].splitlines()) <= 2 for c in cues))
        self.assertTrue(all(c["end"]-c["start"] <= 6 for c in cues))
        self.assertTrue(all(c["end"] <= cues[i+1]["start"] for i,c in enumerate(cues[:-1])))

    def test_invalid_word_times_rejected(self):
        with self.assertRaises(ValueError):
            media.caption_cues([{"word":"a","start":0,"end":1},{"word":"b","start":.5,"end":2}])
        with self.assertRaises(ValueError):
            media.caption_cues([{"word":"a","start":float("nan"),"end":1}])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RenderTests(unittest.TestCase):
    def test_real_render_and_failure_gates(self):
        with tempfile.TemporaryDirectory(prefix="video-editor-test-") as d:
            root = Path(d)
            media.run(["ffmpeg","-v","error","-f","lavfi","-i","color=c=teal:s=640x360","-frames:v","1","-threads","1",str(root/"still.png")])
            media.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=640x360:rate=30","-t","2","-c:v","libx264","-threads","1",str(root/"clip.mp4")])
            media.run(["ffmpeg","-v","error","-f","lavfi","-i","sine=frequency=440:sample_rate=44100","-t","4",str(root/"audio.wav")])
            media.save(root/"words.json", {"words":[{"word":"Caption","start":.1,"end":.6},{"word":"test.","start":.7,"end":1.3},
                                                     {"word":"Second","start":2.1,"end":2.5},{"word":"scene.","start":2.6,"end":3.4}]})
            media.captions(root/"words.json", root/"captions")
            timeline={"width":640,"height":360,"fps":30,"narration":"audio.wav","captions":"captions/captions.srt",
                "shots":[{"id":"s1","path":"still.png","kind":"image","duration":2,"source_url":"synthetic","license":"Generated fixture"},
                         {"id":"s2","path":"clip.mp4","kind":"video","in":0,"duration":2,"fit":"cover","source_url":"synthetic","license":"Generated fixture"}]}
            manifest=root/"timeline.json"
            media.save(manifest,timeline)
            self.assertTrue(media.validate(manifest)["valid"])
            timeline["shots"][1]["in"]=1
            media.save(manifest,timeline)
            self.assertFalse(media.validate(manifest)["valid"])
            timeline["shots"][1]["in"]=0
            timeline["width"]=1280;timeline["height"]=720
            media.save(manifest,timeline)
            self.assertFalse(media.validate(manifest)["valid"])
            self.assertTrue(media.validate(manifest,True)["valid"])
            timeline["width"]=640;timeline["height"]=360
            media.save(manifest,timeline)
            video=root/"v1.mp4"
            media.render(manifest,video)
            info=media.probe(video)
            self.assertAlmostEqual(media.duration(info),4,delta=.1)
            self.assertEqual(next(s for s in info["streams"] if s["codec_type"]=="video")["width"],640)
            with self.assertRaises(ValueError):
                media.render(manifest,video)
            report=media.qa(video,root/"qa",4)
            self.assertTrue(report["decode_ok"])
            self.assertTrue(report["scan_ok"])
            self.assertFalse(report["flags"])
            self.assertFalse(report["publication_ready"])
            media.review(video,root/"review.html")
            self.assertIn('src="v1.mp4"',(root/"review.html").read_text())
            self.assertIn("Export notes",(root/"review.html").read_text())


if __name__=="__main__":
    unittest.main(verbosity=2)
