#!/usr/bin/env python3
"""Evidence-backed production memory. Offline, standard library, no provider billing."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

FACETS = ("script", "thumbnail", "hashtags", "tags", "description", "frames")
METHODS = {"script": {"transcript", "video_analysis"},
           "thumbnail": {"image_inspection"},
           "hashtags": {"metadata"}, "tags": {"metadata"},
           "description": {"metadata"}, "frames": {"video_analysis", "frame_inspection"}}
METRICS = ("viewCount", "vph", "outlierScore")
HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def date(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Dates require a timezone.")
    return d


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label, maximum=1000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum, "Invalid " + label)
    return value.strip()


def public_text(value, label):
    value = text(value, label, 600)
    require(not re.search(r"https?://|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:sk|ghp|github_pat)[_-][\w-]{12,}|(?:/Users/|/home/|[A-Z]:\\)|[\x00-\x08]", value, re.I),
            label + " must be generic learning, without URLs, secrets or private paths.")
    return value


def number(value, label):
    require(type(value) in (float, int) and math.isfinite(value) and value >= 0,
            label + " must be a known, finite nonnegative number.")
    return value


def local(project, relative):
    text(relative, "relative path")
    p = Path(relative)
    require(not p.is_absolute() and ".." not in p.parts, "Use a project-relative path.")
    target = (project / p).resolve()
    require(target.is_relative_to(project.resolve()), "Path escapes the project.")
    require(target.is_file(), "Missing local evidence/artifact: " + relative)
    require(target.stat().st_size <= 20_000_000, "Evidence/artifact exceeds 20 MB.")
    return target


def pointer(value, path):
    require(isinstance(path, str) and (path == "" or path.startswith("/")), "Invalid JSON pointer.")
    for key in path.split("/")[1:]:
        key = key.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            require(re.fullmatch(r"0|[1-9][0-9]*", key), "Invalid array index in JSON pointer.")
            value = value[int(key)]
        else:
            value = value[key]
    return value


@contextmanager
def lock(folder):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Learning update already in progress. Inspect a stranded .lock before recovery.") from None
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


class Learning:
    def __init__(self, home=HERE):
        self.home = Path(home).resolve()
        self.config = read(self.home / "config.json")
        require(self.config["schema_version"] == 1, "Unsupported learning config.")

    def current(self, project):
        project = Path(project).resolve()
        active = read(project / ".evolution" / "active.json")
        run_id = active["run_id"]
        require(re.fullmatch(r"[a-f0-9]{32}", run_id), "Invalid run ID.")
        folder = project / ".evolution" / "runs" / run_id
        run = read(folder / "run.json")
        require(run["repository"] == self.config["repository"], "Run belongs to another repository.")
        return project, folder, run

    def begin(self, project, niche, language, market, video_format):
        project = Path(project).resolve()
        scope = {"niche": public_text(niche, "niche"), "language": text(language, "language", 40),
                 "market": text(market, "market", 40), "format": video_format}
        require(video_format in {"short", "long"}, "Format must be short or long.")
        for key in ("language", "market", "format"):
            expected = self.config.get("fixed_scope", {}).get(key)
            require(expected is None or expected == scope[key], "Repository scope mismatch: " + key)
            public_text(scope[key], key)
        scope_id = digest(scope)[:24]
        knowledge = self.home / "knowledge" / (scope_id + ".json")
        base = read(knowledge) if knowledge.exists() else None
        if base:
            require(base["scope"] == scope, "Knowledge scope mismatch.")
        run = {"schema_version": 1, "run_id": uuid.uuid4().hex, "repository": self.config["repository"],
               "scope": scope, "scope_id": scope_id, "started_at": now(), "phase": "research",
               "base_hash": digest(base), "sync": {"status": "not_attempted"}}
        with lock(project / ".evolution"):
            folder = project / ".evolution" / "runs" / run["run_id"]
            write(folder / "base.json", base)
            write(folder / "run.json", run)
            write(folder / "evidence.template.json", {
                "schema_version": 1, "run_id": run["run_id"], "scope": scope, "collected_at": now(),
                "discovery": {"status": "unavailable", "reason": "Replace with observed collection outcome",
                              "metric": "vph", "age_days": [0, 90], "top_n": 5,
                              "method": "Record queries, search coverage and access limits", "sources": []},
                "videos": [], "lessons": [], "retire": []})
            write(project / ".evolution" / "active.json", {"run_id": run["run_id"]})
        return {**run, "evidence_template": str(folder / "evidence.template.json")}

    def evidence(self, project, run, evidence):
        require(evidence.get("schema_version") == 1, "Unsupported evidence schema.")
        require(evidence["run_id"] == run["run_id"] and evidence["scope"] == run["scope"],
                "Evidence belongs to a different run or scope.")
        at = date(evidence["collected_at"])
        require(date(run["started_at"]) - timedelta(minutes=5) <= at <= date(now()) + timedelta(minutes=5),
                "Evidence must be collected for this run.")
        require(date(now()) - at <= timedelta(hours=72), "Research is stale; start a new run.")
        d = evidence["discovery"]
        require(d["status"] in {"ok", "partial", "unavailable"}, "Invalid discovery status.")
        text(d["method"], "discovery method")
        if d["status"] != "ok":
            text(d.get("reason"), "discovery gap")
        require(d["metric"] in METRICS, "Unsupported ranking metric.")
        low, high = d["age_days"]
        require(0 <= number(low, "minimum age") < number(high, "maximum age") <= 365,
                "Use a declared publication-age cohort, no wider than one year.")
        require(type(d["top_n"]) is int and 1 <= d["top_n"] <= 10, "top_n must be 1 to 10.")
        files = {}

        def source(s):
            p = local(project, s["file"])
            files[s["file"]] = file_hash(p)
            return p

        for s in d["sources"]:
            source(s)
        require(d["status"] == "unavailable" or d["sources"], "Discovery requires saved source results.")
        videos = evidence["videos"]
        require(isinstance(videos, list) and len(videos) <= 100, "Limit the candidate cohort to 100 videos.")
        require(d["status"] != "unavailable" or not videos, "Unavailable discovery cannot contain ranked videos.")
        require(d["status"] == "unavailable" or videos, "Record unavailable when no videos can be verified.")
        seen = set()
        for v in videos:
            require(re.fullmatch(r"[\w-]{11}", v["id"], re.ASCII), "Use a YouTube video ID.")
            require(v["id"] not in seen, "Duplicate video.")
            seen.add(v["id"])
            text(v["channel_id"], "channel ID", 100)
            require(v["scope"] == run["scope"], "Do not mix niches, languages, markets or formats.")
            text(v["scope_basis"], "actual-content scope verification")
            require(v.get("content_verified") is True, "Verify language/format from actual content.")
            observed = date(v["observed_at"])
            require(date(run["started_at"]) - timedelta(minutes=5) <= observed <= at + timedelta(minutes=5),
                    "Use observations collected during this run.")
            raw = pointer(read(source(v["metadata"])), v["metadata"]["pointer"])
            require(raw["id"] == v["id"] and raw["channelId"] == v["channel_id"], "Metadata identity mismatch.")
            published = date(raw["publishedAt"])
            age = (at - published).total_seconds() / 86400
            require(low <= age <= high, "Video outside declared publication-age cohort.")
            value = number(v["metric_value"], "ranking metric")
            raw_value = number(raw.get(d["metric"]), "raw ranking metric")
            require(value == raw_value, "Ranking value differs from saved provider data.")
            require(set(v["facets"]) == set(FACETS), "Record all six facets, including unavailable ones.")
            for facet in FACETS:
                f = v["facets"][facet]
                require(f["status"] in {"observed", "unavailable"}, "Invalid facet status.")
                if f["status"] == "unavailable":
                    text(f.get("reason"), "missing facet reason")
                    continue
                require(f["method"] in METHODS[facet], "Wrong evidence method for " + facet)
                text(f["observation"], "observation", 4000)
                source(f["source"])
                if facet == "thumbnail":
                    image = source({"file": f["image_file"]})
                    require(image.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}, "Save the inspected thumbnail image.")
                if facet in {"hashtags", "tags", "description"}:
                    require(f["source"] == v["metadata"], "Packaging evidence must reference the saved metadata row.")
                    key = "tags" if facet == "tags" else "description"
                    require(raw.get(key) is not None, "Unknown metadata must be unavailable, not empty.")
                    require(isinstance(raw[key], list if facet == "tags" else str), "Invalid metadata field type.")
                if facet in {"script", "frames"}:
                    require(f.get("timestamps"), "Spoken/visual observations need timestamp anchors.")
                    duration = number(v["duration_seconds"], "duration")
                    for t in f["timestamps"]:
                        require(number(t, "timestamp") <= duration, "Timestamp outside video duration.")
                if facet == "frames" and f["method"] == "frame_inspection":
                    require(f.get("frame_files"), "Frame inspection requires saved samples.")
                    for frame in f["frame_files"]:
                        source({"file": frame})
        top = sorted(videos, key=lambda v: (-v["metric_value"], v["id"]))[:d["top_n"]]
        return top, files

    def refresh(self, project, evidence):
        project, folder, run = self.current(project)
        with lock(self.home / "knowledge"):
            evidence_hash = digest(evidence)
            if run["phase"] != "research":
                require(run["evidence_hash"] == evidence_hash, "Run already refreshed; begin a new run for different research.")
                return run
            top, files = self.evidence(project, run, evidence)
            base = read(folder / "base.json")
            target = self.home / "knowledge" / (run["scope_id"] + ".json")
            current = read(target) if target.exists() else None
            require(digest(current) == run["base_hash"] or
                    (current and current.get("run_id") == run["run_id"] and current.get("evidence_hash") == evidence_hash),
                    "Scope memory changed concurrently; begin a new run against its new revision.")
            stamp = evidence["collected_at"]
            by_id = {v["id"]: v for v in top}
            rules = {r["id"]: {**r, "carried_over": True} for r in (base or {}).get("rules", [])
                     if date(r["expires_at"]) > date(stamp)}
            hypotheses, lesson_ids = [], set()
            for lesson in evidence["lessons"]:
                key, facet = lesson["id"], lesson["facet"]
                require(re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", key) and key not in lesson_ids, "Invalid/duplicate lesson ID.")
                lesson_ids.add(key)
                require(facet in FACETS, "Invalid lesson facet.")
                require(key not in rules or rules[key]["facet"] == facet, "A lesson ID cannot change facet.")
                ids = lesson["video_ids"]
                require(isinstance(ids, list) and ids and len(ids) == len(set(ids)), "Use unique supporting videos.")
                require(all(i in by_id and by_id[i]["facets"][facet]["status"] == "observed" for i in ids),
                        "Lessons require observed facets from the ranked sample.")
                channels = {by_id[i]["channel_id"] for i in ids}
                record = {"id": key, "facet": facet,
                          "observation": public_text(lesson["observation"], "lesson observation"),
                          "application": public_text(lesson["application"], "original application"),
                          "sources": ["https://www.youtube.com/watch?v=" + i for i in ids],
                          "independent_channels": len(channels), "verified_at": stamp,
                          "expires_at": (date(stamp) + timedelta(days=30)).isoformat(),
                          "carried_over": False}
                if len(channels) >= 3:
                    rules[key] = record
                else:
                    hypotheses.append(record)
            retired = []
            for item in evidence.get("retire", []):
                require(item["id"] in rules and item["id"] not in lesson_ids, "Retire an existing rule separately from renewing it.")
                facet = rules[item["id"]]["facet"]
                require(item["video_ids"] and all(i in by_id and by_id[i]["facets"][facet]["status"] == "observed"
                                                for i in item["video_ids"]), "Retirement needs relevant observed counterevidence.")
                retired.append({"id": item["id"], "reason": public_text(item["reason"], "retirement reason"),
                                "sources": ["https://www.youtube.com/watch?v=" + i for i in item["video_ids"]]})
                del rules[item["id"]]
            coverage = {f: sum(v["facets"][f]["status"] == "observed" for v in top) for f in FACETS}
            knowledge = {"schema_version": 1, "scope": run["scope"], "revision": (base or {}).get("revision", 0) + 1,
                         "run_id": run["run_id"], "evidence_hash": evidence_hash, "updated_at": stamp,
                         "ranking_metric": evidence["discovery"]["metric"], "age_days": evidence["discovery"]["age_days"],
                         "sample_size": len(top), "coverage": coverage, "rules": list(rules.values()),
                         "hypotheses": hypotheses, "retired": retired,
                         "limits": "Best in the sampled cohort only. Associations, not causal or statistical proof. Missing is unknown."}
            write(folder / "evidence.json", evidence)
            write(folder / "knowledge.json", knowledge)
            write(folder / "sources.json", files)
            brief = ["# Learning brief", "", json.dumps(run["scope"], ensure_ascii=False), "", knowledge["limits"]]
            for facet in FACETS:
                brief += ["", "## " + facet, f"Observed in {coverage[facet]} of {len(top)} sampled videos."]
                applicable = [r for r in rules.values() if r["facet"] == facet]
                for r in applicable:
                    carried = " (carried over; original expiry applies)" if r["carried_over"] else ""
                    brief += [f"- {r['id']}{carried}: {r['application']}"]
                if not applicable:
                    brief.append("No active rule. Use original editorial judgement and record the evidence gap.")
            brief += ["", "Review hypotheses in knowledge.json as experiments only. Never treat them as established defaults."]
            (folder / "brief.md").write_text("\n".join(brief) + "\n", encoding="utf-8")
            write(target, knowledge)
            run.update(phase="refreshed", evidence_hash=evidence_hash, knowledge_hash=digest(knowledge),
                       knowledge_file=str(target.relative_to(self.home)), selected_ids=list(by_id),
                       coverage=coverage, revision=knowledge["revision"])
            write(folder / "run.json", run)
            return run

    def apply(self, project, plan):
        project, folder, run = self.current(project)
        require(run["phase"] != "research", "Refresh evidence before writing the application receipt.")
        require(plan["run_id"] == run["run_id"] and set(plan["facets"]) == set(FACETS),
                "Creation plan must cover all six facets of this run.")
        knowledge = read(folder / "knowledge.json")
        require(digest(knowledge) == run["knowledge_hash"], "Run knowledge changed.")
        artifacts = {}
        for facet in FACETS:
            item = plan["facets"][facet]
            require(".evolution" not in Path(item["artifact"]).parts, "Production artifacts must not reuse raw research files.")
            path = local(project, item["artifact"])
            body = path.read_text(encoding="utf-8")
            require(body.strip(), "Creation artifacts cannot be empty.")
            artifacts[item["artifact"]] = file_hash(path)
            rules = {r["id"] for r in knowledge["rules"] if r["facet"] == facet}
            decisions = item["decisions"]
            require(len({d["rule_id"] for d in decisions}) == len(decisions), "Duplicate application decision.")
            require({d["rule_id"] for d in decisions} == rules, "Address each active rule for " + facet)
            for d in decisions:
                require(d["decision"] in {"applied", "not_applicable"}, "Invalid application decision.")
                text(d["reason"], "application reason")
                if d["decision"] == "applied":
                    excerpt = text(d["excerpt"], "actual artifact excerpt", 2000)
                    require(excerpt in body, "Application excerpt is absent from the creation artifact.")
            if not rules:
                text(item.get("fallback_reason"), "editorial fallback reason")
        inputs = plan.get("production_inputs", [])
        require(isinstance(inputs, list) and len(inputs) == len(set(inputs)), "Use unique production input paths.")
        for relative in inputs:
            require(".evolution" not in Path(relative).parts, "Production inputs must not reuse raw research files.")
            artifacts[relative] = file_hash(local(project, relative))
        require(not set(artifacts).intersection(read(folder / "sources.json")),
                "Production inputs cannot be competitor evidence files.")
        write(folder / "application.json", {"run_id": run["run_id"], "knowledge_hash": run["knowledge_hash"],
                                           "plan": plan, "artifacts": artifacts, "created_at": now()})
        run["phase"] = "applied"
        write(folder / "run.json", run)
        return {"run_id": run["run_id"], "artifacts": artifacts, "status": "applied"}

    def verify(self, project):
        project, folder, run = self.current(project)
        require(run["phase"] == "applied", "Learning not applied to production artifacts.")
        receipt = read(folder / "application.json")
        knowledge = read(folder / "knowledge.json")
        require(receipt["run_id"] == run["run_id"] and receipt["knowledge_hash"] == run["knowledge_hash"] == digest(knowledge),
                "Learning receipt does not match the active run.")
        require(all(date(r["expires_at"]) > date(now()) for r in knowledge["rules"]),
                "Applied rules expired; refresh research before new production work.")
        require(digest(read(folder / "evidence.json")) == run["evidence_hash"], "Research evidence changed.")
        for hashes in (read(folder / "sources.json"), receipt["artifacts"]):
            for relative, expected in hashes.items():
                require(file_hash(local(project, relative)) == expected, "Changed evidence/artifact: " + relative)
        return {"status": "verified", "run_id": run["run_id"], "revision": run["revision"],
                "sync": run["sync"], "note": "Checks provenance and artifact identity, not creative quality, approvals or causality."}

    def sync(self, project):
        """Publish only this run's sanitized knowledge; preserve unrelated changes."""
        project, folder, run = self.current(project)
        require(run["phase"] != "research", "Refresh before syncing.")
        target = self.home / run["knowledge_file"]
        require(digest(read(target)) == run["knowledge_hash"], "Knowledge changed since this run; do not publish it under an old receipt.")
        git_root = self.home

        def git(*args):
            process = subprocess.run(["git", "-C", str(git_root), *args], capture_output=True,
                                     text=True, timeout=45, shell=False)
            # stderr can contain credential-bearing remote URLs; do not persist or echo it.
            require(process.returncode == 0, "Git operation failed: " + args[0] + ". Check local authentication/hooks or remote changes.")
            return process.stdout.strip()

        try:
            root = Path(git("rev-parse", "--show-toplevel")).resolve()
            git_root = root
            path = str(target.relative_to(root))
            require(git("symbolic-ref", "--short", "HEAD") == self.config["branch"], "Use the configured repository branch for learning sync.")
            remote = git("remote", "get-url", "origin")
            expected = self.config["repository"]
            ssh_host = "git@" + "github.com"
            require(remote in {"https://github.com/" + expected, "https://github.com/" + expected + ".git",
                               ssh_host + ":" + expected + ".git", "ssh://" + ssh_host + "/" + expected + ".git"},
                    "Remote does not match the configured repository.")
            branch = self.config["branch"]
            require(re.fullmatch(r"[a-zA-Z0-9_/-]+", branch) and not branch.startswith("-"), "Invalid branch.")
            remote_head = git("ls-remote", "--exit-code", "origin", "refs/heads/" + branch).split()[0]
            head = git("rev-parse", "HEAD")
            pending = run["sync"].get("commit")
            if head != remote_head:
                require(pending == head and git("rev-parse", "HEAD^") == remote_head,
                        "Unpublished commits or remote divergence; reconcile before syncing learning.")
            elif pending != head:
                staged = git("diff", "--cached", "--name-only").splitlines()
                require(not staged or staged == [path], "Unrelated staged changes exist; leave them intact and sync later.")
                dirty = git("status", "--porcelain", "--", path)
                if not dirty:
                    run["sync"] = {"status": "synced", "commit": head}
                    write(folder / "run.json", run)
                    return run["sync"]
                git("add", "--", path)
                git("commit", "--only", "-m", "Learn production patterns for " + run["scope_id"], "--", path)
                head = git("rev-parse", "HEAD")
                require(git("diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines() == [path],
                        "Commit includes unexpected paths; do not push.")
                run["sync"] = {"status": "pending", "commit": head}
                write(folder / "run.json", run)
            if remote_head != head:
                git("push", "origin", "HEAD:refs/heads/" + branch)
            require(git("ls-remote", "--exit-code", "origin", "refs/heads/" + branch).split()[0] == head,
                    "Remote verification failed.")
            run["sync"] = {"status": "synced", "commit": head}
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            run["sync"] = {**run["sync"], "status": "pending", "reason": str(exc)}
        write(folder / "run.json", run)
        return run["sync"]


def verify_if_started(project):
    """Native-tool compatibility: new agent runs must begin; legacy projects still open."""
    if (Path(project) / ".evolution" / "active.json").exists():
        return Learning().verify(project)
    return {"status": "legacy_project", "note": "New productions must begin the learning workflow."}


def verify_for_file(filename):
    """Find the nearest production project for commands taking an artifact path."""
    filename = Path(filename).resolve()
    for parent in filename.parents:
        if (parent / ".evolution" / "active.json").exists():
            engine = Learning()
            result = engine.verify(parent)
            receipt = read(engine.current(parent)[1] / "application.json")
            require(any((parent / relative).resolve() == filename for relative in receipt["artifacts"]),
                    "Production input is not bound to the learning receipt; add it to production_inputs and re-apply.")
            return result
    return {"status": "legacy_project"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("begin")
    p.add_argument("project")
    for field in ("niche", "language", "market", "format"):
        p.add_argument("--" + field, required=True)
    for command in ("refresh", "apply"):
        p = sub.add_parser(command); p.add_argument("project"); p.add_argument("input")
    for command in ("verify", "status", "sync"):
        p = sub.add_parser(command); p.add_argument("project")
    p = sub.add_parser("gate"); p.add_argument("project"); p.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        engine = Learning()
        if args.command == "begin":
            result = engine.begin(args.project, args.niche, args.language, args.market, args.format)
        elif args.command in {"refresh", "apply"}:
            result = getattr(engine, args.command)(args.project, read(args.input))
        elif args.command == "status":
            result = engine.current(args.project)[2]
        elif args.command == "gate":
            engine.verify(args.project)
            command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            require(bool(command), "gate needs a production command after --")
            return subprocess.run(command, shell=False).returncode
        else:
            result = getattr(engine, args.command)(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if args.command == "sync" and result["status"] != "synced" else 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, UnicodeError, subprocess.TimeoutExpired) as exc:
        print("Learning: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
