"""Synthetic offline fixtures: these are not live analytics or creative recommendations."""
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("evolving_learning", Path(__file__).with_name("learn.py"))
learn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(learn)


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "repo" / "evolution"
        self.project = self.root / "project"
        self.config = {"schema_version": 1, "repository": "example/test", "branch": "main", "fixed_scope": {}}
        learn.write(self.home / "config.json", self.config)
        self.engine = learn.Learning(self.home)
        self.run = self.engine.begin(self.project, "Synthetic test niche", "en", "US", "short")
        self.data = self.fixture()

    def fixture(self):
        run = self.engine.current(self.project)[2]
        raw = ".evolution/runs/" + run["run_id"] + "/raw/"
        at = learn.now()
        rows, videos = [], []
        for i in range(3):
            vid = "video00000" + str(i)
            rows.append({"id": vid, "channelId": "channel-" + str(i), "publishedAt":
                         (learn.date(at) - timedelta(days=4)).isoformat(), "vph": 100 + i,
                         "viewCount": 5000 + i, "outlierScore": 2 + i,
                         "description": "Synthetic description #example", "tags": ["example"]})
            metadata = {"file": raw + "metadata.json", "pointer": "/videos/" + str(i)}
            details = {"file": raw + "detail-" + str(i) + ".json", "pointer": ""}
            learn.write(self.project / details["file"], {"video_id": vid, "analysis": "00:01 Synthetic observation"})
            image = raw + "thumbnail-" + str(i) + ".png"
            (self.project / image).write_bytes(b"synthetic image fixture, never live evidence")
            facets = {}
            for facet in learn.FACETS:
                method = {"script": "transcript", "thumbnail": "image_inspection", "frames": "video_analysis"}.get(facet, "metadata")
                facets[facet] = {"status": "observed", "method": method, "observation": "Synthetic test observation",
                                 "source": metadata if method == "metadata" else details,
                                 "timestamps": [1], "image_file": image}
            videos.append({"id": vid, "channel_id": rows[-1]["channelId"], "scope": run["scope"],
                           "scope_basis": "Synthetic content fixture, not a real watch", "content_verified": True,
                           "observed_at": at, "metadata": metadata, "metric_value": rows[-1]["vph"],
                           "duration_seconds": 30, "facets": facets})
        learn.write(self.project / (raw + "metadata.json"), {"videos": rows})
        return {"schema_version": 1, "run_id": run["run_id"], "scope": run["scope"], "collected_at": at,
                "discovery": {"status": "ok", "method": "Synthetic fixture cohort", "metric": "vph",
                              "age_days": [0, 7], "top_n": 3, "sources": [{"file": raw + "metadata.json"}]},
                "videos": videos, "lessons": [{"id": "pattern-" + f, "facet": f,
                    "observation": "Synthetic pattern across independent fixture channels",
                    "application": "Create an original test example with a clear payoff",
                    "video_ids": [v["id"] for v in videos]} for f in learn.FACETS], "retire": []}

    def knowledge(self):
        return learn.read(self.home / "knowledge" / (self.run["scope_id"] + ".json"))

    def plan(self):
        plan = {"run_id": self.run["run_id"], "facets": {}}
        for facet in learn.FACETS:
            filename = facet + ".md"
            (self.project / filename).write_text("Original test concept and payoff for " + facet, encoding="utf-8")
            plan["facets"][facet] = {"artifact": filename, "decisions": [
                {"rule_id": "pattern-" + facet, "decision": "applied", "reason": "Original expression of the finding",
                 "excerpt": "Original test concept"}]}
        return plan

    def complete(self):
        self.engine.refresh(self.project, self.data)
        self.engine.apply(self.project, self.plan())

    def test_full_cycle_six_facets_and_rank(self):
        self.complete()
        self.assertEqual(self.engine.verify(self.project)["status"], "verified")
        self.assertEqual(len(self.knowledge()["rules"]), 6)
        self.assertEqual(self.engine.current(self.project)[2]["selected_ids"][0], "video000002")
        self.assertNotIn("Synthetic description", json.dumps(self.knowledge()))

    def test_wrong_scope_rejected(self):
        self.data["videos"][0]["scope"] = {**self.data["scope"], "format": "long"}
        with self.assertRaisesRegex(ValueError, "mix niches"):
            self.engine.refresh(self.project, self.data)

    def test_json_pointer_rejects_negative_and_noncanonical_indexes(self):
        for pointer in ("/-1", "/01", "/+0"):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                learn.pointer(["a", "b"], pointer)
        self.assertEqual(learn.pointer({"a/b": {"~": 3}}, "/a~1b/~0"), 3)

    def test_no_sources_all_six_fallbacks_can_continue(self):
        empty = learn.read(self.engine.current(self.project)[1] / "evidence.template.json")
        self.engine.refresh(self.project, empty)
        plan = self.plan()
        for item in plan["facets"].values():
            item["decisions"] = []
            item["fallback_reason"] = "No supported finding; follow original editorial judgement"
        self.engine.apply(self.project, plan)
        self.assertEqual(self.engine.verify(self.project)["status"], "verified")
        self.assertEqual(self.knowledge()["sample_size"], 0)

    def test_fixed_language_rejected(self):
        learn.write(self.home / "config.json", {**self.config, "fixed_scope": {"language": "ja"}})
        with self.assertRaisesRegex(ValueError, "scope mismatch"):
            learn.Learning(self.home).begin(self.project, "Another niche", "en", "US", "short")

    def test_scope_histories_isolated(self):
        self.engine.refresh(self.project, self.data)
        new = self.engine.begin(self.root / "other", "Another niche", "en", "US", "short")
        self.assertNotEqual(new["scope_id"], self.run["scope_id"])
        self.assertIsNone(learn.read(Path(new["evidence_template"]).with_name("base.json")))

    def test_stale_research_rejected(self):
        self.data["collected_at"] = (learn.date(learn.now()) - timedelta(days=8)).isoformat()
        with self.assertRaisesRegex(ValueError, "this run"):
            self.engine.refresh(self.project, self.data)

    def test_future_observation_rejected(self):
        self.data["videos"][0]["observed_at"] = (learn.date(learn.now()) + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "during this run"):
            self.engine.refresh(self.project, self.data)

    def test_metric_cannot_be_invented(self):
        self.data["videos"][0]["metric_value"] = 999999
        with self.assertRaisesRegex(ValueError, "differs"):
            self.engine.refresh(self.project, self.data)

    def test_missing_metric_is_not_zero(self):
        p = self.project / self.data["videos"][0]["metadata"]["file"]
        raw = learn.read(p); raw["videos"][0]["vph"] = None; learn.write(p, raw)
        with self.assertRaisesRegex(ValueError, "known"):
            self.engine.refresh(self.project, self.data)

    def test_age_cohort_enforced(self):
        self.data["discovery"]["age_days"] = [0, 2]
        with self.assertRaisesRegex(ValueError, "publication-age"):
            self.engine.refresh(self.project, self.data)

    def test_content_verification_required(self):
        self.data["videos"][0]["content_verified"] = False
        with self.assertRaisesRegex(ValueError, "actual content"):
            self.engine.refresh(self.project, self.data)

    def test_transcript_cannot_establish_frames(self):
        self.data["videos"][0]["facets"]["frames"]["method"] = "transcript"
        with self.assertRaisesRegex(ValueError, "Wrong evidence method"):
            self.engine.refresh(self.project, self.data)

    def test_thumbnail_requires_saved_image(self):
        self.data["videos"][0]["facets"]["thumbnail"]["image_file"] = "missing.jpg"
        with self.assertRaisesRegex(ValueError, "Missing local"):
            self.engine.refresh(self.project, self.data)

    def test_frame_inspection_requires_samples(self):
        self.data["videos"][0]["facets"]["frames"]["method"] = "frame_inspection"
        with self.assertRaisesRegex(ValueError, "saved samples"):
            self.engine.refresh(self.project, self.data)

    def test_timestamp_bounds(self):
        self.data["videos"][0]["facets"]["frames"]["timestamps"] = [99]
        with self.assertRaisesRegex(ValueError, "outside"):
            self.engine.refresh(self.project, self.data)

    def test_null_tags_not_empty_tags(self):
        p = self.project / self.data["videos"][0]["metadata"]["file"]
        raw = learn.read(p); raw["videos"][0]["tags"] = None; learn.write(p, raw)
        with self.assertRaisesRegex(ValueError, "Unknown metadata"):
            self.engine.refresh(self.project, self.data)
        raw["videos"][0]["tags"] = []; learn.write(p, raw)
        self.engine.refresh(self.project, self.data)

    def test_unavailable_facet_is_coverage_gap(self):
        for v in self.data["videos"]:
            v["facets"]["thumbnail"] = {"status": "unavailable", "reason": "No image access"}
        self.data["lessons"] = [l for l in self.data["lessons"] if l["facet"] != "thumbnail"]
        self.engine.refresh(self.project, self.data)
        self.assertEqual(self.knowledge()["coverage"]["thumbnail"], 0)

    def test_same_channel_is_not_independent_support(self):
        p = self.project / self.data["videos"][0]["metadata"]["file"]
        raw = learn.read(p)
        for i, v in enumerate(self.data["videos"]):
            v["channel_id"] = raw["videos"][i]["channelId"] = "same-channel"
        learn.write(p, raw)
        self.engine.refresh(self.project, self.data)
        self.assertFalse(self.knowledge()["rules"])
        self.assertEqual(len(self.knowledge()["hypotheses"]), 6)

    def test_lesson_cannot_cite_outside_top_sample(self):
        self.data["discovery"]["top_n"] = 1
        with self.assertRaisesRegex(ValueError, "ranked sample"):
            self.engine.refresh(self.project, self.data)

    def test_secret_like_lesson_rejected(self):
        self.data["lessons"][0]["application"] = "Contact private.person" + "@" + "example.test"
        with self.assertRaisesRegex(ValueError, "generic learning"):
            self.engine.refresh(self.project, self.data)

    def test_path_traversal_and_symlink_rejected(self):
        outside = self.root / "outside.json"; outside.write_text("{}")
        (self.project / "escape.json").symlink_to(outside)
        for path in ("../outside.json", "escape.json", str(outside)):
            with self.subTest(path=path), self.assertRaises(ValueError):
                learn.local(self.project, path)

    def test_refresh_idempotent_but_not_rewriteable(self):
        a = self.engine.refresh(self.project, self.data)
        self.assertEqual(self.engine.refresh(self.project, self.data), a)
        self.data["lessons"][0]["application"] = "Changed recommendation"
        with self.assertRaisesRegex(ValueError, "already refreshed"):
            self.engine.refresh(self.project, self.data)

    def test_concurrent_scope_update_rejected(self):
        other = self.root / "other-project"
        self.engine.begin(other, "Synthetic test niche", "en", "US", "short")
        self.engine.refresh(self.project, self.data)
        # The second run holds revision zero; reject it even when provider access fails.
        template = learn.read(self.engine.current(other)[1] / "evidence.template.json")
        with self.assertRaisesRegex(ValueError, "concurrently"):
            self.engine.refresh(other, template)

    def test_unavailable_does_not_refresh_old_verification_date(self):
        self.engine.refresh(self.project, self.data)
        previous = self.knowledge()["rules"][0]
        self.engine.begin(self.project, "Synthetic test niche", "en", "US", "short")
        template = learn.read(self.engine.current(self.project)[1] / "evidence.template.json")
        self.engine.refresh(self.project, template)
        carried = self.knowledge()["rules"][0]
        self.assertTrue(carried["carried_over"])
        self.assertEqual(carried["expires_at"], previous["expires_at"])
        self.assertEqual(carried["verified_at"], previous["verified_at"])

    def test_old_rules_expire(self):
        self.engine.refresh(self.project, self.data)
        target = self.home / "knowledge" / (self.run["scope_id"] + ".json")
        old = learn.read(target)
        for r in old["rules"]:
            r["expires_at"] = (learn.date(learn.now()) - timedelta(days=1)).isoformat()
        learn.write(target, old)
        self.engine.begin(self.project, "Synthetic test niche", "en", "US", "short")
        template = learn.read(self.engine.current(self.project)[1] / "evidence.template.json")
        self.engine.refresh(self.project, template)
        self.assertFalse(self.knowledge()["rules"])

    def test_application_requires_all_facets_and_rules(self):
        self.engine.refresh(self.project, self.data)
        plan = self.plan(); del plan["facets"]["tags"]
        with self.assertRaisesRegex(ValueError, "all six"):
            self.engine.apply(self.project, plan)
        plan = self.plan(); plan["facets"]["script"]["decisions"] = []
        with self.assertRaisesRegex(ValueError, "each active rule"):
            self.engine.apply(self.project, plan)

    def test_application_requires_real_excerpt(self):
        self.engine.refresh(self.project, self.data)
        plan = self.plan(); plan["facets"]["script"]["decisions"][0]["excerpt"] = "Absent quote"
        with self.assertRaisesRegex(ValueError, "excerpt is absent"):
            self.engine.apply(self.project, plan)

    def test_changed_script_invalidates_gate(self):
        self.complete()
        (self.project / "script.md").write_text("Changed script")
        with self.assertRaisesRegex(ValueError, "Changed evidence/artifact"):
            self.engine.verify(self.project)

    def test_changed_raw_evidence_invalidates_gate(self):
        self.complete()
        (self.project / self.data["videos"][0]["metadata"]["file"]).write_text("{}")
        with self.assertRaisesRegex(ValueError, "Changed evidence/artifact"):
            self.engine.verify(self.project)

    def test_production_before_apply_rejected(self):
        self.engine.refresh(self.project, self.data)
        with self.assertRaisesRegex(ValueError, "not applied"):
            self.engine.verify(self.project)

    def test_raw_competitor_source_cannot_be_production_artifact(self):
        self.engine.refresh(self.project, self.data)
        plan = self.plan()
        plan["facets"]["script"]["artifact"] = self.data["videos"][0]["metadata"]["file"]
        with self.assertRaisesRegex(ValueError, "raw research"):
            self.engine.apply(self.project, plan)

    def test_native_file_must_be_bound_and_revisions_invalidate_it(self):
        self.complete()
        target = self.project / "render-plan.json"; target.write_text('{"original": true}')
        with patch.object(learn, "Learning", return_value=self.engine):
            with self.assertRaisesRegex(ValueError, "not bound"):
                learn.verify_for_file(target)
            plan = self.plan(); plan["production_inputs"] = [target.name]
            self.engine.apply(self.project, plan)
            self.assertEqual(learn.verify_for_file(target)["status"], "verified")
            target.write_text('{"changed": true}')
            with self.assertRaisesRegex(ValueError, "Changed evidence/artifact"):
                learn.verify_for_file(target)

    def test_equivalent_relative_input_paths_are_accepted(self):
        self.engine.refresh(self.project, self.data)
        plan = self.plan()
        plan["facets"]["script"]["artifact"] = "./script.md"
        self.engine.apply(self.project, plan)
        with patch.object(learn, "Learning", return_value=self.engine):
            self.assertEqual(learn.verify_for_file(self.project / "script.md")["status"], "verified")

    def test_sync_without_git_records_pending(self):
        self.engine.refresh(self.project, self.data)
        self.assertEqual(self.engine.sync(self.project)["status"], "pending")

    def setup_git(self):
        repo = self.home.parent
        remote = self.root / "remote.git"
        run = subprocess.run

        def git(*args, cwd=repo):
            return run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

        git("init", "-b", "main")
        git("config", "user.name", "Learning Test")
        git("config", "user.email", "test" + "@" + "example.test")
        git("add", "."); git("commit", "-m", "Baseline")
        git("init", "--bare", str(remote))
        git("remote", "add", "origin", str(remote))
        git("push", "-u", "origin", "main")

        def transport(argv, **kwargs):
            if argv[3:6] == ["remote", "get-url", "origin"]:
                return subprocess.CompletedProcess(argv, 0, "https://github.com/example/test.git\n", "")
            return run(argv, **kwargs)
        return git, transport, remote

    def test_sync_only_learning_and_idempotent_retry(self):
        git, transport, remote = self.setup_git()
        (self.home.parent / "unrelated.txt").write_text("Leave alone")
        self.engine.refresh(self.project, self.data)
        with patch.object(learn.subprocess, "run", side_effect=transport):
            result = self.engine.sync(self.project)
            self.assertEqual(result["status"], "synced", result)
            self.assertEqual(self.engine.sync(self.project), result)
        names = git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
        self.assertEqual(names, ["evolution/knowledge/" + self.run["scope_id"] + ".json"])
        self.assertIn("unrelated.txt", git("status", "--porcelain"))
        self.assertEqual(git("rev-parse", "HEAD"), git("rev-parse", "main", cwd=remote))

    def test_sync_preserves_unrelated_staged_changes(self):
        git, transport, _ = self.setup_git()
        (self.home.parent / "unrelated.txt").write_text("Keep staged")
        git("add", "unrelated.txt")
        self.engine.refresh(self.project, self.data)
        with patch.object(learn.subprocess, "run", side_effect=transport):
            result = self.engine.sync(self.project)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(git("diff", "--cached", "--name-only"), "unrelated.txt")

    def test_sync_refuses_unpublished_user_commits(self):
        git, transport, _ = self.setup_git()
        (self.home.parent / "unrelated.txt").write_text("Local work")
        git("add", "unrelated.txt"); git("commit", "-m", "User work")
        self.engine.refresh(self.project, self.data)
        with patch.object(learn.subprocess, "run", side_effect=transport):
            result = self.engine.sync(self.project)
        self.assertEqual(result["status"], "pending")
        self.assertIn("Unpublished commits", result["reason"])

    def test_failed_push_can_resume_exact_learning_commit(self):
        git, transport, _ = self.setup_git()
        self.engine.refresh(self.project, self.data)
        def fail_push(argv, **kwargs):
            if argv[3] == "push":
                return subprocess.CompletedProcess(argv, 1, "", "secret-bearing diagnostics are discarded")
            return transport(argv, **kwargs)
        with patch.object(learn.subprocess, "run", side_effect=fail_push):
            pending = self.engine.sync(self.project)
        self.assertEqual(pending["status"], "pending")
        self.assertNotIn("secret-bearing", json.dumps(pending))
        with patch.object(learn.subprocess, "run", side_effect=transport):
            done = self.engine.sync(self.project)
        self.assertEqual(done["status"], "synced", done)
        self.assertEqual(done["commit"], pending["commit"])


if __name__ == "__main__":
    unittest.main()
